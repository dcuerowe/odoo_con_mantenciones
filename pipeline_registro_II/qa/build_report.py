"""Convierte el JUnit XML de una corrida de pytest en qa/RESULTADOS.md.

Uso:
  RUN_ODOO_INTEGRATION=1 .venv/bin/python -m pytest qa/scaffolding --junitxml=/tmp/qa_run/junit.xml
  .venv/bin/python qa/build_report.py /tmp/qa_run/junit.xml
"""

import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

XML = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/qa_run/junit.xml")
OBJ = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/qa_run/objetos.json")
OUT = Path(__file__).resolve().parent / "RESULTADOS.md"

MODEL_NAMES = {
    "maintenance.request": "Solicitud de mantención",
    "maintenance.equipment": "Equipo",
    "x_inbox_integracion": "Registro de inbox",
    "ir.attachment": "Adjunto (PDF)",
}

LEVELS = {"unit": ("L1", "Unitario (funciones puras, sin red)"),
          "component": ("L2", "Componente (OdooSpy, sin red)"),
          "integration": ("L3", "Integración (test-Odoo real, staging)")}
MOD_NAMES = {
    "test_data_processing": "ordenar_respuestas",
    "test_check_new_sub": "check_new_sub (dedup)",
    "test_process_entrys_mc": "MC — Correctiva",
    "test_process_entrys_cf": "CF — Configuración",
    "test_process_entrys_mp": "MP — Preventiva",
    "test_process_entrys_i": "I — Instalación",
    "test_process_entrys_r": "R — Reemplazo/Extracción",
    "test_smoke_test_odoo": "Smoke (solo lectura)",
    "test_e2e_escritura": "E2E escritura — MC",
    "test_e2e_flujos": "E2E escritura — por flujo",
}

tree = ET.parse(XML)
_root = tree.getroot()
suite = _root.find("testsuite")
if suite is None:
    suite = _root
attr = suite.attrib
total = int(attr.get("tests", 0))
failures = int(attr.get("failures", 0))
errors = int(attr.get("errors", 0))
skipped = int(attr.get("skipped", 0))
passed = total - failures - errors - skipped
duration = float(attr.get("time", 0.0))
ts = attr.get("timestamp", datetime.now().isoformat())[:19].replace("T", " ")


def outcome(tc):
    if tc.find("failure") is not None:
        return "FALLÓ"
    if tc.find("error") is not None:
        return "ERROR"
    if tc.find("skipped") is not None:
        return "OMITIDA"
    return "PASÓ"


# Agrupar: nivel -> módulo -> [(test, outcome, time)]
data = {}
for tc in suite.iter("testcase"):
    cls = tc.get("classname", "")
    seg = cls.split(".")
    level_key = next((s for s in seg if s in LEVELS), "component")
    mod_key = seg[-1]
    data.setdefault(level_key, {}).setdefault(mod_key, []).append(
        (tc.get("name"), outcome(tc), float(tc.get("time", 0.0))))

lines = []
A = lines.append
A("# Reporte de Resultados de Pruebas — QA Integración Connecteam → Odoo")
A("")
A(f"> Generado el **{ts}** a partir de una corrida real de pytest "
  f"(Python {sys.version.split()[0]}, pytest {__import__('pytest').__version__}).")
A("> Este archivo es **evidencia reproducible**: se regenera con los comandos del final.")
A("")
A("## Resumen")
A("")
estado = "TODAS EN VERDE" if (failures + errors) == 0 else f"{failures + errors} CON FALLO"
A(f"- **Estado: {estado}**")
A(f"- Total: **{total}** · Pasaron: **{passed}** · Fallaron: **{failures}** · "
  f"Errores: **{errors}** · Omitidas: **{skipped}**")
A(f"- Duración total: **{duration:.1f} s**")
A("")
A("| Nivel | Descripción | Pruebas | Pasaron | Fallaron | Omitidas |")
A("|-------|-------------|--------:|--------:|---------:|---------:|")
for lk in ("unit", "component", "integration"):
    if lk not in data:
        continue
    tcs = [t for m in data[lk].values() for t in m]
    p = sum(1 for _, o, _ in tcs if o == "PASÓ")
    f = sum(1 for _, o, _ in tcs if o in ("FALLÓ", "ERROR"))
    sk = sum(1 for _, o, _ in tcs if o == "OMITIDA")
    code, desc = LEVELS[lk]
    A(f"| {code} | {desc} | {len(tcs)} | {p} | {f} | {sk} |")
A("")
A("## Detalle por nivel y módulo")
A("")
for lk in ("unit", "component", "integration"):
    if lk not in data:
        continue
    code, desc = LEVELS[lk]
    A(f"### {code} · {desc}")
    A("")
    for mod_key in sorted(data[lk]):
        tcs = data[lk][mod_key]
        nombre = MOD_NAMES.get(mod_key, mod_key)
        p = sum(1 for _, o, _ in tcs if o == "PASÓ")
        A(f"**{nombre}** — {p}/{len(tcs)} ({mod_key}.py)")
        A("")
        A("| Prueba | Resultado | Tiempo (s) |")
        A("|--------|-----------|-----------:|")
        for name, oc, tm in tcs:
            A(f"| `{name}` | {oc} | {tm:.2f} |")
        A("")

# --- Objetos creados en el test-Odoo (vinculación con registros reales) ---
objetos = []
if OBJ.exists():
    try:
        objetos = json.loads(OBJ.read_text(encoding="utf-8"))
    except Exception:
        objetos = []

A("## Objetos creados en el test-Odoo")
A("")
if not objetos:
    A("_Esta corrida no escribió en el test-Odoo (solo L1+L2, o no se capturaron objetos)._")
    A("")
else:
    A(f"Durante la corrida se crearon **{len(objetos)}** registros reales en el test-Odoo "
      "(staging), vinculados a la prueba que los originó. No se limpian.")
    A("")
    # Resumen por modelo
    por_modelo = {}
    for o in objetos:
        por_modelo.setdefault(o["model"], []).append(o["id"])
    A("| Modelo Odoo | Tipo | Cantidad | IDs |")
    A("|-------------|------|---------:|-----|")
    for model, ids in sorted(por_modelo.items()):
        nombre = MODEL_NAMES.get(model, model)
        ids_txt = ", ".join(str(i) for i in ids)
        if len(ids_txt) > 70:
            ids_txt = ids_txt[:67] + "..."
        A(f"| `{model}` | {nombre} | {len(ids)} | {ids_txt} |")
    A("")
    # Detalle por prueba
    A("**Detalle por prueba:**")
    A("")
    A("| Prueba | Modelo | ID | Referencia |")
    A("|--------|--------|---:|------------|")
    for o in objetos:
        nombre = MODEL_NAMES.get(o["model"], o["model"])
        A(f"| `{o['test']}` | {nombre} | {o['id']} | {o.get('label') or '—'} |")
    A("")

A("## Notas")
A("")
A("- **L3 escribe en el test-Odoo (staging):** los E2E ejecutan `process_entrys` de "
  "punta a punta y crean registros reales (inbox, solicitudes) y mueven equipos QA. "
  "No se limpian; se acumulan al re-ejecutar (OTs 990xxx, equipos QA 1496-1500).")
A("- **Oráculo positivo:** cada prueba afirma un efecto observable (llamada/valor en "
  "Odoo o en el spy), no solo la ausencia de excepción.")
A("- Defectos encontrados y su estado: ver "
  "[`docs/09_matriz_trazabilidad.md`](docs/09_matriz_trazabilidad.md) §4 (incluye OBS-10, corregido).")
A("")
A("## Cómo regenerar este reporte")
A("")
A("```bash")
A("PY=/Users/dacm/we/.venv/bin/python")
A("# L1+L2+L3 (incluye escritura en staging):")
A("RUN_ODOO_INTEGRATION=1 $PY -m pytest qa/scaffolding --junitxml=/tmp/qa_run/junit.xml")
A("$PY qa/build_report.py /tmp/qa_run/junit.xml")
A("")
A("# Solo L1+L2 (sin tocar Odoo): omitir RUN_ODOO_INTEGRATION y agregar -m \"not integration\"")
A("```")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"OK -> {OUT}  ({total} pruebas, {passed} pasaron, {failures + errors} fallos, {skipped} omitidas)")
