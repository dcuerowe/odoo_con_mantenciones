"""
Generador manual de informes PDF (report_generator.informe_pdf_profesional).

Dos modos:
  (1) Indicar una OT → la busca en Connecteam. Primero mira las últimas 20
      submissions (rápido); si la OT no está ahí, pide un rango de fechas y
      pagina Connecteam por ese rango para recuperar OTs antiguas. Luego detecta
      las combinaciones (punto, tipo de trabajo, equipo) presentes, extrae los 16
      campos del PDF y te deja editar antes de generar.
  (2) Formulario manual desde cero: te pide los 16 campos uno por uno.

Los PDFs se guardan en pipeline_registro_II/informes_pdf/ con el mismo formato
de nombre que usa processor.py:
  informe_OT-{ot}_{punto}_{tipo}_{equipo}.pdf            # MC, CF
  informe_OT-{ot}_{punto}_{tipo}_{subtipo}_{equipo}.pdf  # I, MP, R

R (reemplazo) tiene dos subtipos: E=extracción, I=instalación del reemplazo.
report_generator no conoce 'R', así que al generar el PDF se traduce al subtipo.
"""

import re
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from config import CONNECTEAM_API_KEY
from connecteam_api import (
    all_submission,
    form_structure,
    submissions_by_date_range,
    user as resolve_user,
)
from data_processing import ordenar_respuestas
from report_generator import informe_pdf_profesional


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "informes_pdf"
CHILE_TZ = ZoneInfo("America/Santiago")
# Tipos de trabajo seleccionables. R (reemplazo) no lo conoce report_generator:
# se traduce a su subtipo (E=extracción, I=instalación) al generar el PDF.
VALID_TRABAJOS = ("MC", "MP", "I", "CF", "R")
I_TRANSLATE = {"I": "dispositivo", "T": "tablero"}
MP_TRANSLATE = {"I": "Dispositivo", "T": "Tablero"}
R_SUBTIPOS = ("E", "I")  # E = extracción, I = instalación del reemplazo

PDF_ARG_ORDER = (
    "numero_visita", "ot", "tecnico", "proyecto", "fecha", "cliente",
    "tipo_equipo", "modelo", "serial", "trabajo", "alcance", "punto",
    "obs_especifica", "obs_generales", "imagenes", "equipo",
)


# ---------------------------------------------------------------------------
# Connecteam fetch + detección
# ---------------------------------------------------------------------------

def _date_range_to_epoch(start_str, end_str):
    """Convierte un rango 'YYYY-MM-DD' (hora de Chile) a (start, end) en epoch
    SEGUNDOS. El rango cubre desde las 00:00:00 del día inicial hasta las
    23:59:59 del día final (inclusive)."""
    start = datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=CHILE_TZ)
    end = datetime.strptime(end_str, "%Y-%m-%d").replace(tzinfo=CHILE_TZ)
    start_epoch = int(start.timestamp())
    end_epoch = int((end + timedelta(days=1)).timestamp()) - 1
    return start_epoch, end_epoch


def fetch_ot_dataframe(ot, date_range=None):
    """Devuelve la fila correspondiente al # OT pedido. None si no aparece.

    - date_range=None            -> últimas 20 submissions (rápido, camino por
      defecto; solo alcanza OTs recientes).
    - date_range=(desde, hasta)  -> ambos 'YYYY-MM-DD'; pagina por rango de fecha
      en Connecteam, permitiendo recuperar OTs antiguas."""
    schema = form_structure(CONNECTEAM_API_KEY)
    if date_range is None:
        subs = all_submission(CONNECTEAM_API_KEY)
    else:
        start_epoch, end_epoch = _date_range_to_epoch(*date_range)
        subs = submissions_by_date_range(CONNECTEAM_API_KEY, start_epoch, end_epoch)
    df = ordenar_respuestas(schema, subs)
    if df.empty or "#" not in df.columns:
        return None
    df_ot = df[df["#"] == ot]
    if df_ot.empty:
        return None
    return df_ot.iloc[[0]].copy()


def detect_combinations(df_ot):
    """Devuelve lista de tuplas (punto, tipo, subtipo|None, equipo_idx) detectadas."""
    combos = set()
    cols = list(df_ot.columns)
    patterns = [
        (re.compile(r"^(\d+)\.2\.(\d+) MC \|"),         lambda m: (m.group(1), "MC", None, m.group(2))),
        (re.compile(r"^(\d+)\.2\.(\d+) CF \|"),         lambda m: (m.group(1), "CF", None, m.group(2))),
        (re.compile(r"^(\d+)\.2\.(\d+) I \((I|T)\) \|"),lambda m: (m.group(1), "I",  m.group(3), m.group(2))),
        (re.compile(r"^(\d+)\.2\.(\d+) MP \((I|T)\) \|"),lambda m: (m.group(1), "MP", m.group(3), m.group(2))),
        (re.compile(r"^(\d+)\.2\.(\d+) R \((I|E)\) \|"),lambda m: (m.group(1), "R",  m.group(3), m.group(2))),
    ]
    for c in cols:
        for pat, builder in patterns:
            m = pat.match(c)
            if m:
                combos.add(builder(m))
                break
    return sorted(combos)


# ---------------------------------------------------------------------------
# Extracción de campos (replica exacta de processor.py para cada tipo)
# ---------------------------------------------------------------------------

def _get(row, col, default=""):
    if col in row.index:
        v = row[col]
        return v if v is not None else default
    return default


def extract_fields(df_ot, punto_i, trabajo, subtipo, equipo_idx):
    row = df_ot.iloc[0]
    ot = int(row["#"])

    # Datos generales del punto
    punto_full = str(_get(row, f"{punto_i}.1 Punto de monitoreo", ""))
    m = re.search(r"\[([^\]]*)\]", punto_full)
    proyecto = m.group(1) if m else str(_get(row, f"{punto_i}.1 Proyecto", ""))
    punto = re.sub(r"\[[^\]]*\]", "", punto_full).strip()

    fecha = str(_get(row, "Fecha visita ", ""))
    cliente = str(_get(row, "Nombre del Cliente", ""))
    obs_generales = str(_get(row, f"{punto_i}.3 Resolución de visita", ""))
    imagenes = _get(row, f"{punto_i}.4 Fotos recinto", [])
    if not isinstance(imagenes, list):
        imagenes = []

    # Técnico
    user_id = row.get("user")
    try:
        tecnico = resolve_user(CONNECTEAM_API_KEY, user_id) if user_id else "Usuario no encontrado"
    except Exception:
        tecnico = f"Usuario {user_id}"

    # Campos específicos por tipo (column names exactos de processor.py)
    prefix = f"{punto_i}.2.{equipo_idx}"
    if trabajo == "MC":
        modelo = _get(row, f"{prefix} MC | Modelo")
        tipo_equipo = _get(row, f"{prefix} MC | Activo a intervenir")
        serial = _get(row, f"{prefix} MC | N° de serie")
        obs_esp = _get(row, f"{prefix} MC | Observación")
        alcance = False
    elif trabajo == "CF":
        modelo = _get(row, f"{prefix} CF | Modelo")
        tipo_equipo = _get(row, f"{prefix} CF | Activo a intervenir")
        serial = _get(row, f"{prefix} CF | N° de serie")
        obs_esp = _get(row, f"{prefix} CF | Observación")
        alcance = _get(row, f"{prefix} CF | Tipo de Ajuste")
    elif trabajo == "I":
        t = subtipo
        modelo = _get(row, f"{prefix} I ({t}) | Modelo")
        tipo_equipo = _get(row, f"{prefix} I ({t}) | Tipo de {I_TRANSLATE[t]}")
        serial = _get(row, f"{prefix} I ({t}) | N° de serie")
        obs_esp = _get(row, f"{prefix} I ({t}) | Observación")
        alcance = ("IH | Habilitación de equipo" if t == "I"
                   else _get(row, f"{prefix} I (T) | Alcance de la intervención"))
    elif trabajo == "MP":
        t = subtipo
        modelo = _get(row, f"{prefix} MP ({t}) | Modelo")
        tipo_equipo = _get(row, f"{prefix} MP ({t}) | {MP_TRANSLATE[t]} a intervenir")
        serial = _get(row, f"{prefix} MP ({t}) | N° de serie")
        obs_esp = _get(row, f"{prefix} MP ({t}) | Observación")
        alcance = False
    elif trabajo == "R":
        # Reemplazo: campos generales en "R |", específicos en "R (E|I) |".
        t = subtipo  # E = extracción, I = instalación del reemplazo
        modelo = _get(row, f"{prefix} R ({t}) | Modelo")
        tipo_equipo = _get(row, f"{prefix} R | Tipo equipo/instrumento a reemplazar")
        serial = _get(row, f"{prefix} R ({t}) | N° de serie")
        obs_esp = _get(row, f"{prefix} R | Observación")
        alcance = _get(row, f"{prefix} R | Motivo de reemplazo")
    else:
        raise ValueError(f"Trabajo no soportado por el PDF: {trabajo}")

    return {
        "numero_visita": punto_i,
        "ot": ot,
        "tecnico": str(tecnico),
        "proyecto": str(proyecto),
        "fecha": fecha,
        "cliente": str(cliente),
        "tipo_equipo": str(tipo_equipo),
        "modelo": str(modelo),
        "serial": str(serial),
        "trabajo": trabajo,
        "alcance": alcance,
        "punto": str(punto),
        "obs_especifica": str(obs_esp),
        "obs_generales": str(obs_generales),
        "imagenes": imagenes,
        "equipo": int(equipo_idx),
        # Metadata extra, no va al PDF — se usa para nombrar el archivo
        "_subtipo": subtipo,
    }


# ---------------------------------------------------------------------------
# Editor interactivo de campos
# ---------------------------------------------------------------------------

def _display(v):
    if isinstance(v, list):
        return f"<lista con {len(v)} elemento(s)>"
    if v is False:
        return "False"
    s = str(v)
    return s if len(s) <= 70 else s[:67] + "..."


def edit_fields(fields):
    keys = [k for k in fields.keys() if not k.startswith("_")]
    while True:
        print("\n--- Campos actuales ---")
        for idx, k in enumerate(keys):
            print(f"  [{idx:2d}] {k:18s} = {_display(fields[k])}")
        raw = input("\n# a editar (enter = listo, 'q' = abortar): ").strip()
        if raw == "":
            return fields
        if raw.lower() == "q":
            return None
        try:
            idx = int(raw)
            k = keys[idx]
        except (ValueError, IndexError):
            print("Índice inválido.")
            continue
        nv = input(f"Nuevo valor para {k} (enter = mantener): ")
        if nv == "":
            continue
        fields[k] = _coerce(k, nv)
        print(f"OK → {k} = {_display(fields[k])}")


def _coerce(key, raw):
    if key in ("ot", "equipo"):
        try:
            return int(raw)
        except ValueError:
            print("(no es entero, se guarda como texto)")
            return raw
    if key == "imagenes":
        return [u.strip() for u in raw.split(",") if u.strip()]
    if key == "alcance" and raw.lower() in ("false", "f", "none"):
        return False
    if key == "trabajo":
        v = raw.strip().upper()
        if v not in VALID_TRABAJOS:
            print(f"⚠ trabajo {v!r} no está en {VALID_TRABAJOS}; el PDF puede fallar.")
        return v
    return raw


# ---------------------------------------------------------------------------
# Generación y guardado
# ---------------------------------------------------------------------------

_SANITIZE = re.compile(r'[<>:"/\\|?*\s]+')


def output_path(fields):
    OUTPUT_DIR.mkdir(exist_ok=True)
    punto_safe = _SANITIZE.sub("_", str(fields["punto"]) or "sin_punto").strip("_")
    sub = fields.get("_subtipo")
    if sub:
        name = f"informe_OT-{fields['ot']}_{punto_safe}_{fields['trabajo']}_{sub}_{fields['equipo']}.pdf"
    else:
        name = f"informe_OT-{fields['ot']}_{punto_safe}_{fields['trabajo']}_{fields['equipo']}.pdf"
    return OUTPUT_DIR / name


def _normalize_fecha(s):
    """report_generator._formatear_fecha espera '%Y-%m-%d %H:%M:%S' (UTC) para
    convertir a hora de Chile. Acepta también '%Y-%m-%d' y le anexa 00:00:00;
    si no parsea, el informe usa el texto tal cual sin reventar."""
    from datetime import datetime
    s = (str(s) or "").strip()
    for fmt_in in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt_in)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return s  # se la pasamos tal cual; el PDF reventará y veremos el error


def _pdf_trabajo(fields):
    """report_generator.informe_pdf_profesional no conoce 'R'; para reemplazos
    el código que espera es el subtipo (E=extracción, I=instalación)."""
    trabajo = fields["trabajo"]
    if trabajo == "R":
        sub = fields.get("_subtipo")
        return sub if sub in R_SUBTIPOS else "E"
    return trabajo


def generate_pdf(fields):
    fields = dict(fields)
    fields["fecha"] = _normalize_fecha(fields.get("fecha", ""))
    args = [fields[k] for k in PDF_ARG_ORDER]
    # El nombre de archivo conserva 'R'; el PDF recibe el subtipo traducido.
    args[PDF_ARG_ORDER.index("trabajo")] = _pdf_trabajo(fields)
    buf = informe_pdf_profesional(*args)
    path = output_path(fields)
    with open(path, "wb") as f:
        f.write(buf.getvalue())
    print(f"\n-> PDF guardado en {path.relative_to(BASE_DIR)}")
    return path


# ---------------------------------------------------------------------------
# Modo 1 — búsqueda en Connecteam
# ---------------------------------------------------------------------------

def _ask_date_range():
    """Pide un rango de fechas 'YYYY-MM-DD'. Devuelve (desde, hasta) o None si se
    cancela / el formato es inválido. 'hasta' vacío = hoy."""
    print("\nIngresa un rango de fechas para buscar más atrás (formato YYYY-MM-DD).")
    desde = input("  Desde (vacío = cancelar): ").strip()
    if not desde:
        return None
    hoy = date.today().isoformat()
    hasta = input(f"  Hasta (vacío = hoy {hoy}): ").strip() or hoy
    try:
        datetime.strptime(desde, "%Y-%m-%d")
        datetime.strptime(hasta, "%Y-%m-%d")
    except ValueError:
        print("Formato de fecha inválido (usa YYYY-MM-DD).")
        return None
    if desde > hasta:
        print("'Desde' es posterior a 'Hasta'.")
        return None
    return (desde, hasta)


def search_mode():
    raw = input("\n# OT a buscar en Connecteam: ").strip()
    try:
        ot = int(raw)
    except ValueError:
        print("OT debe ser entero.")
        return

    print("Buscando en las últimas 20 submissions de Connecteam...")
    df_ot = fetch_ot_dataframe(ot)

    if df_ot is None:
        print(f"OT {ot} no está entre las últimas 20 submissions.")
        date_range = _ask_date_range()
        if date_range is None:
            return
        print(f"Buscando OT {ot} entre {date_range[0]} y {date_range[1]} "
              "(esto pagina Connecteam, puede tardar)...")
        df_ot = fetch_ot_dataframe(ot, date_range=date_range)
        if df_ot is None:
            print(f"OT {ot} no aparece en el rango {date_range[0]} a {date_range[1]}.")
            return

    combos = detect_combinations(df_ot)
    if not combos:
        print("No se detectaron combinaciones (MC/CF/I/MP) en esta OT.")
        return

    print(f"\nCombinaciones detectadas para OT {ot}:")
    for idx, (i, t, st, eq) in enumerate(combos):
        st_str = f" ({st})" if st else ""
        print(f"  [{idx}] punto {i} · {t}{st_str} · equipo {eq}")

    raw = input("\nÍndices separados por coma (vacío = todos): ").strip()
    if raw:
        try:
            selected = [combos[int(x.strip())] for x in raw.split(",")]
        except (ValueError, IndexError):
            print("Selección inválida.")
            return
    else:
        selected = combos

    for combo in selected:
        i, t, st, eq = combo
        print(f"\n========== Combo: punto {i} · {t}{f' ({st})' if st else ''} · equipo {eq} ==========")
        try:
            fields = extract_fields(df_ot, i, t, st, eq)
        except Exception as e:
            print(f"Error extrayendo campos: {e}")
            traceback.print_exc()
            continue
        fields = edit_fields(fields)
        if fields is None:
            print("Combo abortado, sigo con el siguiente.")
            continue
        try:
            generate_pdf(fields)
        except Exception as e:
            print(f"Error generando PDF: {e}")
            traceback.print_exc()


# ---------------------------------------------------------------------------
# Modo 2 — formulario manual desde cero
# ---------------------------------------------------------------------------

def _ask(label, default=""):
    raw = input(f"{label} [{default}]: ").strip()
    return raw if raw else default


def manual_form():
    print(f"\nTrabajos válidos: {', '.join(VALID_TRABAJOS)}")
    print("(Subtipo: MP/I -> I=Instrumento, T=Tablero · R -> E=Extracción, I=Instalación.)")

    try:
        ot = int(_ask("ot (entero)"))
    except ValueError:
        print("OT inválida.")
        return None

    trabajo = ""
    while trabajo not in VALID_TRABAJOS:
        trabajo = input(f"trabajo ({'/'.join(VALID_TRABAJOS)}): ").strip().upper()

    subtipo = None
    if trabajo in ("MP", "I"):
        while subtipo not in ("I", "T"):
            subtipo = input("subtipo (I=Instrumento, T=Tablero): ").strip().upper()
    elif trabajo == "R":
        while subtipo not in R_SUBTIPOS:
            subtipo = input("subtipo (E=Extracción, I=Instalación): ").strip().upper()

    alcance_raw = _ask("alcance (vacío/'false' = False)", "")
    alcance = False if alcance_raw.lower() in ("", "false", "f") else alcance_raw

    img_raw = input("imágenes (URLs separadas por coma, vacío = sin imágenes): ").strip()
    imagenes = [u.strip() for u in img_raw.split(",") if u.strip()]

    fields = {
        "numero_visita": _ask("numero_visita (dígito del punto, ej '1')", "1"),
        "ot": ot,
        "tecnico": _ask("tecnico (nombre)"),
        "proyecto": _ask("proyecto"),
        "fecha": _ask("fecha (YYYY-MM-DD)"),
        "cliente": _ask("cliente"),
        "tipo_equipo": _ask("tipo_equipo (Sonda multiparamétrica, Caudalímetro, ...)"),
        "modelo": _ask("modelo"),
        "serial": _ask("serial"),
        "trabajo": trabajo,
        "alcance": alcance,
        "punto": _ask("punto (nombre del punto)"),
        "obs_especifica": _ask("observaciones al equipo"),
        "obs_generales": _ask("observaciones generales"),
        "imagenes": imagenes,
        "equipo": int(_ask("equipo (índice 1, 2, ...)", "1") or "1"),
        "_subtipo": subtipo,
    }
    return fields


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    while True:
        print("""
============================================
  Generador manual de informes PDF
============================================
(1) Buscar OT en Connecteam y generar
(2) Formulario manual desde cero
(3) Salir
""")
        codigo = input("> ").strip()
        try:
            if codigo == "1":
                search_mode()
            elif codigo == "2":
                fields = manual_form()
                if fields is None:
                    continue
                fields = edit_fields(fields)
                if fields is None:
                    print("Abortado.")
                    continue
                generate_pdf(fields)
            elif codigo == "3":
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
