"""L2 · Componente — Verificación del manejo de S/N numérico con cero a la izquierda.

Escenario solicitado: OT 260, punto de monitoreo "ET-0F".

En Odoo NO existen S/N numéricos que empiecen por 0, pero el formulario de
Connecteam puede traer el serial tipeado como "04245245". `normalizar_serial`
ahora elimina el cero líder, de modo que la búsqueda en Odoo se hace contra
"4245245" (el serial real) y el equipo SÍ se encuentra.

Estas pruebas ejercitan el flujo completo `process_entrys` (módulo MC) con el
spy de Odoo y afirman que:
  1. El dominio del search_read sobre maintenance.equipment usa "4245245" y
     NUNCA el "04245245" original (cero líder eliminado).
  2. Con el serial normalizado el equipo se encuentra y se crea la solicitud
     (no cae en la rama 'S/N no encontrado').
"""

import pandas as pd
import pytest

import processor

OT = 260
PUNTO = "ET-0F"
PROYECTO = "Las Tórtolas"
LOC = f"[{PROYECTO}] {PUNTO}"          # ubicación coincidente -> sin notificación de cambio
SERIAL_FORM = "04245245"              # como llega del formulario (cero a la izquierda)
SERIAL_ODOO = "4245245"               # como existe realmente en Odoo

ACC_COLS = ("OT", "Técnico", "Fecha de revisión", "Proyecto", "Punto de monitoreo",
            "Equipo/instrumento", "Modelo", "N° serie", "Tipo", "Mensaje")


def _df_ot260(serial=SERIAL_FORM, operativo="Sí"):
    """DataFrame de una visita MC: OT 260, punto 'ET-0F [Las Tórtolas]'."""
    row = {
        "#": OT, "user": 42, "Fecha visita ": "2026-06-05 10:00:00",
        "Nombre del Cliente": "Cliente QA",
        "1.1 Punto de monitoreo": f"{PUNTO} [{PROYECTO}]",
        "1.2 Tipo de trabajo a realizar": "MC",
        "1.3 Resolución de visita": "Visita OK",
        "1.4 Fotos recinto": ["sim://foto1"],
        "1.2.1 MC | Modelo": "Modelo-QA",
        "1.2.1 MC | Activo a intervenir": "Caudalímetro",
        "1.2.1 MC | N° de serie": serial,
        "1.2.1 MC | ¿Equipo operativo tras trabajos?": operativo,
        "1.2.1 MC | Observación": "obs QA",
    }
    return pd.DataFrame([row])


def _equipo():
    """Equipo real en Odoo: serial numérico SIN cero a la izquierda."""
    return [{"id": 42, "serial_no": SERIAL_ODOO, "x_studio_location": [7, LOC]}]


def _run(spy, df):
    resumen = {k: [] for k in ACC_COLS}
    exito = {k: [] for k in ACC_COLS}
    processor.process_entrys(df, "KEY", resumen, exito, spy)
    return resumen, exito


def _inbox(spy, field):
    return [r.get(field) for r in spy.created("x_inbox_integracion")]


# --------------------------------------------------------------------------- #
# 1. El cero líder se elimina antes de consultar Odoo.
# --------------------------------------------------------------------------- #
def test_ot260_serial_cero_se_normaliza_antes_de_buscar(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", [])  # no nos importa el resultado
    spy.set_default("search_read", "x_maintenance_location", [])
    _run(spy, _df_ot260())

    eq = spy.calls_of("search_read", "maintenance.equipment")
    assert eq, spy.dump()
    dominio = eq[0].args[0]
    valores = [c[2] for c in dominio if isinstance(c, (list, tuple)) and len(c) == 3]

    # El valor buscado es el serial SIN cero líder...
    assert any(isinstance(v, str) and SERIAL_ODOO in v for v in valores), \
        f"se esperaba '{SERIAL_ODOO}' en el dominio, fue {dominio}"
    # ...y en ningún caso aparece el "04245245" original.
    for v in valores:
        if isinstance(v, str):
            assert SERIAL_FORM not in v, \
                f"el cero líder NO debió llegar a Odoo, dominio: {dominio}"


# --------------------------------------------------------------------------- #
# 2. Con el serial normalizado el equipo se encuentra y se crea la solicitud.
# --------------------------------------------------------------------------- #
def test_ot260_serial_cero_encuentra_equipo_y_crea_solicitud(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo())
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    # search('maintenance.request') -> [] por defecto => no hay solicitud activa => crear
    _run(spy, _df_ot260(operativo="Sí"))

    creates = spy.created("maintenance.request")
    assert creates, "el equipo debió encontrarse y crear la solicitud\n" + spy.dump()
    v = creates[0]
    assert v.get("equipment_id") == 42
    assert v.get("x_studio_tipo_de_trabajo") == "Mantención Correctiva"

    # No debe haberse notificado 'S/N no encontrado'.
    mensajes = [r.get("x_studio_mensaje", "") or "" for r in spy.created("x_inbox_integracion")]
    assert not any("no encontrado" in m.lower() for m in mensajes), \
        f"no debió caer en 'S/N no encontrado': {mensajes}"

    # Ubicación coincide ([Las Tórtolas] ET-0F) => sin aviso de cambio de ubicación.
    assert spy.calls_of("message_post", "maintenance.equipment") == [], spy.dump()
