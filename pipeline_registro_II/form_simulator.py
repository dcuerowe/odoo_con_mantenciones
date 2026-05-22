"""
Simulador de formularios Connecteam.

Lee la estructura del formulario desde form.json (respuesta cruda de
connecteam_api.form_structure(), shape {"data": {"questions": [...]}}) y permite
construir submissions interactivamente con la misma forma que devuelve
all_submission(). Las submissions resultantes se guardan en simulated_submissions/
y pueden ejecutarse a través del pipeline real (ordenar_respuestas + process_entrys)
contra el Odoo configurado en .env.

Comandos disponibles en cualquier prompt de respuesta:
  :skip   → marca la pregunta como wasHidden=True (igual que respuesta vacía)
  :done   → cierra el formulario; todas las preguntas restantes quedan hidden
  :abort  → descarta el formulario y vuelve al menú

Nota sobre lógica condicional: Connecteam NO incluye reglas de visibilidad
en la respuesta de form_structure(). El simulador no puede deducirlas — usá
:done o :skip para reflejar a mano qué preguntas no aplicarían en cada caso.
"""

import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import tabulate

from config import (
    CONNECTEAM_API_KEY,
    ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD,
)
from odoo_client import OdooClient
from data_processing import ordenar_respuestas
from processor import process_entrys


BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "form.json"
SUBMISSIONS_DIR = BASE_DIR / "simulated_submissions"
CHILE_TZ = ZoneInfo("America/Santiago")

CMD_SKIP = ":skip"
CMD_DONE = ":done"
CMD_ABORT = ":abort"


class DoneSignal(Exception):
    """El usuario pidió cerrar el formulario; el resto queda hidden."""


class AbortSignal(Exception):
    """El usuario pidió abortar; volver al menú."""


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------

def load_schema():
    if not SCHEMA_PATH.exists() or SCHEMA_PATH.stat().st_size == 0:
        raise FileNotFoundError(
            f"\n{SCHEMA_PATH} está vacío o no existe.\n"
            "Pega la respuesta de connecteam_api.form_structure() en ese archivo."
        )
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def flatten_questions(questions):
    """Aplana grupos a una lista de preguntas atómicas (excluye los nodos 'group'
    intermedios pero los anota con su título para que el resumen los muestre)."""
    flat = []
    def walk(qs, group_path):
        for q in qs:
            if q.get("questionType") == "group" and "questions" in q:
                walk(q["questions"], group_path + [q.get("title", q["questionId"])])
            else:
                flat.append((group_path, q))
    walk(questions, [])
    return flat


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_int(s, default=None):
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


def parse_datetime_to_epoch(s, with_date=True, with_time=True):
    s = (s or "").strip()
    fmts = []
    if with_date and with_time:
        fmts = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")
    elif with_date:
        fmts = ("%Y-%m-%d",)
    elif with_time:
        fmts = ("%H:%M:%S", "%H:%M")
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            if not with_date:
                # Anclar a hoy si solo es hora
                today = datetime.now(CHILE_TZ).date()
                dt = dt.replace(year=today.year, month=today.month, day=today.day)
            return int(dt.replace(tzinfo=CHILE_TZ).timestamp())
        except ValueError:
            continue
    raise ValueError(f"Formato inválido: {s!r}.")


def _strip_html(s):
    """Quita tags muy simples para que los títulos en description sean legibles."""
    import re
    return re.sub(r"<[^>]+>", "", s or "").strip()


def prompt_with_commands(label):
    """input() centralizado para poder atajar :done / :abort en cualquier prompt."""
    raw = input(label).strip()
    if raw == CMD_DONE:
        raise DoneSignal()
    if raw == CMD_ABORT:
        raise AbortSignal()
    return raw


# ---------------------------------------------------------------------------
# Per-type collectors
# ---------------------------------------------------------------------------

def _hidden(q):
    return {
        "questionId": q["questionId"],
        "questionType": q["questionType"],
        "wasSubmittedEmpty": False,
        "wasHidden": True,
    }


def _required_warning(q, raw):
    """Avisa si la pregunta era obligatoria y el usuario la salta."""
    if q.get("submissionRequired") and raw in ("", CMD_SKIP):
        print("  ⚠ Esta pregunta es obligatoria; quedará marcada como hidden de todos modos.")


def collect_openended(q, base):
    raw = prompt_with_commands("respuesta (texto libre, vacío = hidden): ")
    _required_warning(q, raw)
    if raw in ("", CMD_SKIP):
        return _hidden(q)
    return {**base, "value": raw}


def collect_yesno(q, base):
    opts = q.get("allAnswers") or [{"yesNoOptionId": 0, "text": "Sí"},
                                    {"yesNoOptionId": 1, "text": "No"}]
    for opt in opts:
        print(f"  [{opt['yesNoOptionId']}] {opt['text']}")
    raw = prompt_with_commands("respuesta (0/1 o texto, vacío = hidden): ")
    _required_warning(q, raw)
    if raw in ("", CMD_SKIP):
        return _hidden(q)
    # Match por índice
    i = parse_int(raw)
    if i in (0, 1):
        return {**base, "selectedIndex": i}
    # Match por texto
    lr = raw.lower()
    for opt in opts:
        if opt["text"].lower() == lr or lr in ("si", "sí", "s", "y", "yes") and opt["yesNoOptionId"] == 0 \
           or lr in ("no", "n") and opt["yesNoOptionId"] == 1:
            return {**base, "selectedIndex": opt["yesNoOptionId"]}
    print("  Respuesta no reconocida; quedará como hidden.")
    return _hidden(q)


def collect_multiple_choice(q, base):
    opts = q.get("allAnswers") or []
    is_multi = bool(q.get("isMultipleSelect"))
    for idx, opt in enumerate(opts):
        print(f"  [{idx}] {opt['text']}")
    label = ("respuesta (índices separados por coma, vacío = hidden): "
             if is_multi else
             "respuesta (un índice, vacío = hidden): ")
    raw = prompt_with_commands(label)
    _required_warning(q, raw)
    if raw in ("", CMD_SKIP):
        return _hidden(q)
    choices_raw = raw.split(",") if is_multi else [raw]
    selected = []
    for c in choices_raw:
        c = c.strip()
        if not c:
            continue
        i = parse_int(c)
        if i is not None and 0 <= i < len(opts):
            selected.append({"text": opts[i]["text"]})
        else:
            # texto libre / "Otro"
            selected.append({"text": c})
    if not selected:
        return _hidden(q)
    return {**base, "selectedAnswers": selected}


def collect_datetime(q, base):
    with_date = q.get("isDateActive", True)
    with_time = q.get("isTimeActive", True)
    if with_date and with_time:
        hint = "YYYY-MM-DD HH:MM"
    elif with_date:
        hint = "YYYY-MM-DD"
    else:
        hint = "HH:MM"
    raw = prompt_with_commands(f"respuesta (formato {hint}, vacío = hidden): ")
    _required_warning(q, raw)
    if raw in ("", CMD_SKIP):
        return _hidden(q)
    try:
        ts = parse_datetime_to_epoch(raw, with_date=with_date, with_time=with_time)
    except ValueError as e:
        print(f"  {e}  → queda como hidden.")
        return _hidden(q)
    return {**base, "timestamp": ts}


def collect_rating(q, base):
    lo, hi = q.get("minValue", 1), q.get("maxValue", 5)
    print(f"  Escala: {lo} ({q.get('minValueText','')}) … {hi} ({q.get('maxValueText','')})")
    raw = prompt_with_commands(f"respuesta (entero entre {lo} y {hi}, vacío = hidden): ")
    _required_warning(q, raw)
    if raw in ("", CMD_SKIP):
        return _hidden(q)
    val = parse_int(raw)
    if val is None or not (lo <= val <= hi):
        print(f"  Fuera de rango [{lo},{hi}]; queda como hidden.")
        return _hidden(q)
    return {**base, "ratingValue": val}


def collect_image(q, base):
    multi = q.get("isMultipleImageUploadAllowed", False)
    label = ("respuesta (URLs separadas por coma, vacío = hidden): "
             if multi else
             "respuesta (una URL, vacío = hidden): ")
    raw = prompt_with_commands(label)
    _required_warning(q, raw)
    if raw in ("", CMD_SKIP):
        return _hidden(q)
    urls = [u.strip() for u in raw.split(",") if u.strip()] if multi else [raw]
    return {**base, "images": [{"url": u} for u in urls]}


def collect_signature(q, base):
    raw = prompt_with_commands("¿firma capturada? (s/n, vacío = hidden): ").lower()
    _required_warning(q, raw)
    if raw in ("", CMD_SKIP):
        return _hidden(q)
    has_sig = raw in ("s", "si", "sí", "y", "yes", "1")
    return {**base, "images": [{"url": "simulated://signature"}] if has_sig else []}


COLLECTORS = {
    "openEnded": collect_openended,
    "yesNo": collect_yesno,
    "multipleChoice": collect_multiple_choice,
    "datetime": collect_datetime,
    "rating": collect_rating,
    "image": collect_image,
    "signature": collect_signature,
}


def collect_answer(q):
    """Devuelve el answer dict para una pregunta atómica (no-group)."""
    q_type = q["questionType"]
    title = _strip_html(q.get("title", "")) or f"Pregunta {q['questionId']}"
    req = " *" if q.get("submissionRequired") else ""
    print(f"\n--- {title}{req}   [{q_type}]")
    if q.get("description"):
        desc = _strip_html(q["description"])
        if desc:
            print(f"    ({desc})")

    if q_type == "description":
        return {**_hidden(q), "wasHidden": False, "wasSubmittedEmpty": True}

    base = {
        "questionId": q["questionId"],
        "questionType": q_type,
        "wasSubmittedEmpty": False,
        "wasHidden": False,
    }
    collector = COLLECTORS.get(q_type)
    if collector is None:
        # Tipo desconocido: fallback texto libre
        return collect_openended(q, base)
    return collector(q, base)


# ---------------------------------------------------------------------------
# Walker con soporte de :done
# ---------------------------------------------------------------------------

def _mark_remaining_hidden(questions):
    """Convierte preguntas restantes en answers wasHidden=True respetando 'group'."""
    out = []
    for q in questions:
        if q.get("questionType") == "group" and "questions" in q:
            out.append({
                "questionId": q["questionId"],
                "questionType": "group",
                "wasSubmittedEmpty": False,
                "wasHidden": False,
                "answers": _mark_remaining_hidden(q["questions"]),
            })
        elif q.get("questionType") == "description":
            out.append({**_hidden(q), "wasHidden": False, "wasSubmittedEmpty": True})
        else:
            out.append(_hidden(q))
    return out


def collect_for_questions(questions, done_flag):
    """Recorre preguntas; respeta DoneSignal — todo lo restante queda hidden."""
    answers = []
    for idx, q in enumerate(questions):
        if done_flag["done"]:
            answers.extend(_mark_remaining_hidden(questions[idx:]))
            return answers

        if q.get("questionType") == "group" and "questions" in q:
            print(f"\n=== Grupo: {_strip_html(q.get('title', q['questionId']))} ===")
            nested = collect_for_questions(q["questions"], done_flag)
            answers.append({
                "questionId": q["questionId"],
                "questionType": "group",
                "wasSubmittedEmpty": False,
                "wasHidden": False,
                "answers": nested,
            })
        else:
            try:
                answers.append(collect_answer(q))
            except DoneSignal:
                done_flag["done"] = True
                answers.extend(_mark_remaining_hidden(questions[idx + 1:]))
                return answers
    return answers


# ---------------------------------------------------------------------------
# Resumen + edición
# ---------------------------------------------------------------------------

def _answer_display_value(ans):
    """Replica extraer_valor() para mostrar el valor humano en el resumen."""
    if ans.get("wasHidden"):
        return "<hidden>"
    if ans.get("wasSubmittedEmpty"):
        return "<vacío>"
    t = ans.get("questionType")
    if t == "openEnded":
        return ans.get("value", "")
    if t == "yesNo":
        idx = ans.get("selectedIndex")
        return "Sí" if idx == 0 else "No" if idx == 1 else str(idx)
    if t == "multipleChoice":
        return ", ".join(o["text"] for o in ans.get("selectedAnswers", []))
    if t == "datetime":
        ts = ans.get("timestamp")
        if ts:
            return datetime.fromtimestamp(ts, tz=CHILE_TZ).strftime("%Y-%m-%d %H:%M")
        return ""
    if t == "rating":
        return ans.get("ratingValue", "")
    if t == "image":
        return f"{len(ans.get('images', []))} imagen(es)"
    if t == "signature":
        return "Firma" if ans.get("images") else "Sin firma"
    return ""


def _flatten_answers(answers, group_path=None):
    """Aplana respuestas (siguiendo groups) a una lista [(group_path, answer)]."""
    group_path = group_path or []
    out = []
    for ans in answers:
        if ans.get("questionType") == "group":
            out.extend(_flatten_answers(ans.get("answers", []), group_path + [ans["questionId"]]))
        else:
            out.append((group_path, ans))
    return out


def _build_id_to_title(schema_questions):
    out = {}
    def walk(qs):
        for q in qs:
            out[q["questionId"]] = _strip_html(q.get("title", ""))
            if "questions" in q:
                walk(q["questions"])
    walk(schema_questions)
    return out


def show_summary(submission, schema_questions):
    id_to_title = _build_id_to_title(schema_questions)
    sub = submission["data"]["formSubmissions"][0]
    rows = []
    answered = []
    for i, (_, ans) in enumerate(_flatten_answers(sub["answers"])):
        title = id_to_title.get(ans["questionId"], "?")
        val = _answer_display_value(ans)
        if ans.get("wasHidden"):
            continue
        if ans.get("questionType") == "description":
            continue
        rows.append([i, title[:60], val])
        answered.append(ans["questionId"])
    print("\n========== Resumen de respuestas (no-hidden) ==========")
    print(f"OT (#): {sub['entryNum']}   user: {sub['submittingUserId']}   "
          f"ts: {datetime.fromtimestamp(sub['submissionTimestamp'], tz=CHILE_TZ).strftime('%Y-%m-%d %H:%M')}")
    print(tabulate.tabulate(rows, headers=["#", "Pregunta", "Valor"], tablefmt="grid"))
    return answered


def find_question_by_id(schema_questions, qid):
    for q in schema_questions:
        if q["questionId"] == qid:
            return q
        if "questions" in q:
            found = find_question_by_id(q["questions"], qid)
            if found:
                return found
    return None


def replace_answer_in_tree(answers, qid, new_answer):
    for i, ans in enumerate(answers):
        if ans.get("questionType") == "group":
            if replace_answer_in_tree(ans.get("answers", []), qid, new_answer):
                return True
        elif ans["questionId"] == qid:
            answers[i] = new_answer
            return True
    return False


def edit_loop(submission, schema_questions):
    """Permite editar respuestas por número de fila del resumen."""
    sub = submission["data"]["formSubmissions"][0]
    while True:
        answered_ids = show_summary(submission, schema_questions)
        if not answered_ids:
            print("No hay respuestas para editar.")
            return
        raw = input("\n# a editar (enter = terminar): ").strip()
        if not raw:
            return
        idx = parse_int(raw)
        if idx is None or not (0 <= idx < len(answered_ids)):
            print("Índice inválido.")
            continue
        qid = answered_ids[idx]
        q = find_question_by_id(schema_questions, qid)
        if not q:
            print("No encontré la pregunta en el schema.")
            continue
        try:
            new_ans = collect_answer(q)
        except (DoneSignal, AbortSignal):
            return
        replace_answer_in_tree(sub["answers"], qid, new_ans)


# ---------------------------------------------------------------------------
# Build / persist / pipeline
# ---------------------------------------------------------------------------

def build_submission(schema):
    questions = schema.get("data", {}).get("questions", [])
    if not questions:
        raise ValueError("form.json no contiene data.questions[].")

    print("\n========== Datos generales ==========")
    entry_num = None
    while not entry_num:
        try:
            raw = prompt_with_commands("# entryNum (número de OT, entero): ")
        except (DoneSignal, AbortSignal):
            raise AbortSignal()
        entry_num = parse_int(raw)

    try:
        user_id = parse_int(prompt_with_commands("submittingUserId (id Connecteam del técnico): "), 0)
        ts_raw = prompt_with_commands("submissionTimestamp [YYYY-MM-DD HH:MM, vacío = ahora]: ")
    except AbortSignal:
        raise
    ts = parse_datetime_to_epoch(ts_raw) if ts_raw else int(time.time())

    print(f"\n========== Respuestas  (comandos: {CMD_SKIP}, {CMD_DONE}, {CMD_ABORT}) ==========")
    print(f"Total de preguntas top-level: {len(questions)}.")
    print("Connecteam no entrega reglas de visibilidad en el schema → usá :done/:skip")
    print("para reflejar qué no aplica.")

    done_flag = {"done": False}
    answers = collect_for_questions(questions, done_flag)

    return {
        "data": {
            "formSubmissions": [{
                "entryNum": entry_num,
                "submittingUserId": user_id,
                "submissionTimestamp": ts,
                "answers": answers,
            }]
        }
    }


def save_submission(submission):
    SUBMISSIONS_DIR.mkdir(exist_ok=True)
    sub = submission["data"]["formSubmissions"][0]
    path = SUBMISSIONS_DIR / f"sim_OT-{sub['entryNum']}_{int(time.time())}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(submission, f, ensure_ascii=False, indent=2)
    print(f"\n-> Guardado en {path.relative_to(BASE_DIR)}")
    return path


def load_submission_interactive():
    SUBMISSIONS_DIR.mkdir(exist_ok=True)
    files = sorted(SUBMISSIONS_DIR.glob("*.json"))
    if not files:
        print("No hay archivos en simulated_submissions/.")
        return None
    print("\nSubmissions disponibles:")
    for idx, p in enumerate(files):
        print(f"  [{idx}] {p.name}")
    raw = input("\nÍndice (o ruta a otro archivo): ").strip()
    idx = parse_int(raw)
    if idx is not None and 0 <= idx < len(files):
        path = files[idx]
    else:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Columnas que processor.process_entrys exige sí o sí (ver processor.py:107 y
# referencias a 'Fecha visita ', 'Nombre del Cliente', etc.).
PIPELINE_REQUIRED_GLOBAL = ("Fecha visita ", "Nombre del Cliente")
PIPELINE_REQUIRED_PER_POINT = (
    "{i}.1 Punto de monitoreo",
    "{i}.2 Tipo de trabajo a realizar",
    "{i}.3 Resolución de visita",
    "{i}.4 Fotos recinto",
)


def validate_for_pipeline(df):
    """Devuelve lista de columnas requeridas que faltan en el DataFrame producido
    por ordenar_respuestas(). Si está vacía, el pipeline debería poder arrancar."""
    missing = []
    for col in PIPELINE_REQUIRED_GLOBAL:
        if col not in df.columns:
            missing.append(col)
    visited = sorted({c[0] for c in df.columns if c and isinstance(c, str) and c[:1].isdigit()})
    if not visited:
        missing.append("(ningún punto visitado: no hay columnas que empiecen con dígito)")
    for i in visited:
        for tmpl in PIPELINE_REQUIRED_PER_POINT:
            col = tmpl.format(i=i)
            if col not in df.columns:
                missing.append(col)
    return missing


def confirm_writes_to_odoo():
    ans = input("\n¡Esto ESCRIBE en Odoo! Continuar? [s/N]: ").strip().lower()
    return ans in ("s", "si", "sí", "y", "yes")


def run_pipeline(submission, schema, odoo):
    df = ordenar_respuestas(schema, submission)
    if df.empty:
        print("ordenar_respuestas() devolvió un DataFrame vacío.")
        return
    print("\nDataFrame plano resultante:")
    print(tabulate.tabulate(df, headers="keys", tablefmt="grid"))

    missing = validate_for_pipeline(df)
    if missing:
        print("\n⚠ Faltan columnas que processor.process_entrys exige:")
        for col in missing:
            print(f"   - {col!r}")
        print("Volvé al menú, editá la submission y respondé esas preguntas antes de correr el pipeline.")
        return

    cols = ('OT','Técnico','Fecha de revisión','Proyecto','Punto de monitoreo',
            'Equipo/instrumento','Modelo','N° serie','Tipo','Mensaje')
    resumen = {k: [] for k in cols}
    exito = {k: [] for k in cols}
    process_entrys(df, CONNECTEAM_API_KEY, resumen, exito, odoo)
    print("\nResumen (manual):")
    print(tabulate.tabulate(pd.DataFrame(resumen), headers="keys", tablefmt="grid"))
    print("\nResumen (éxito):")
    print(tabulate.tabulate(pd.DataFrame(exito), headers="keys", tablefmt="grid"))


def connect_odoo():
    odoo = OdooClient(ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD)
    odoo.authenticate()
    return odoo


def finalize_submission(submission, schema):
    """Resumen + acción: guardar / editar / descartar."""
    questions = schema["data"]["questions"]
    while True:
        show_summary(submission, questions)
        # Pre-check de columnas que el pipeline necesita
        df_preview = ordenar_respuestas(schema, submission)
        missing = validate_for_pipeline(df_preview) if not df_preview.empty else ["(submission vacía)"]
        if missing:
            print("\n⚠ Si querés correr el pipeline (opción 2 o 3), faltan estas columnas:")
            for col in missing:
                print(f"   - {col!r}")
            print("Podés guardar igual, pero process_entrys va a fallar hasta que las completes.")
        print("\n(g) guardar    (e) editar una respuesta    (d) descartar")
        op = input("> ").strip().lower()
        if op == "g":
            return True
        if op == "e":
            edit_loop(submission, questions)
        elif op == "d":
            return False
        else:
            print("Opción inválida.")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    try:
        schema = load_schema()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"\nError al cargar form.json: {e}")
        sys.exit(1)

    print(f"Form cargado: {schema['data'].get('formName','?')} "
          f"({len(schema['data']['questions'])} preguntas top-level)")
    odoo = None

    while True:
        print("""
============================================
  Simulador de formularios Connecteam
============================================
(1) Generar nueva submission y guardar JSON
(2) Cargar submission desde JSON y correr pipeline
(3) Generar y correr en un solo paso
(4) Salir
""")
        codigo = input("Indique un código: ").strip()

        try:
            if codigo == "1":
                try:
                    sub = build_submission(schema)
                except AbortSignal:
                    print("Abortado.")
                    continue
                if finalize_submission(sub, schema):
                    save_submission(sub)
                else:
                    print("Descartado.")

            elif codigo == "2":
                sub = load_submission_interactive()
                if sub is None:
                    continue
                if not confirm_writes_to_odoo():
                    continue
                if odoo is None:
                    odoo = connect_odoo()
                run_pipeline(sub, schema, odoo)

            elif codigo == "3":
                try:
                    sub = build_submission(schema)
                except AbortSignal:
                    print("Abortado.")
                    continue
                if not finalize_submission(sub, schema):
                    print("Descartado.")
                    continue
                save_submission(sub)
                if not confirm_writes_to_odoo():
                    continue
                if odoo is None:
                    odoo = connect_odoo()
                run_pipeline(sub, schema, odoo)

            elif codigo == "4":
                print("Saliendo...")
                break

            else:
                print("Opción inválida.")

        except KeyboardInterrupt:
            print("\nCancelado. Volviendo al menú.")
        except Exception as e:
            print(f"\nError: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
