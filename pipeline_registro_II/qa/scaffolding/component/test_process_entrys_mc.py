"""L2 · Componente — process_entrys, módulo MC (Mantención Correctiva), TODAS las ramas.

Niveles de rama cubiertos (ver docs/04_modulo_MC.md y processor.py L283-944):

  S/N NO encontrado:
    - punto inexistente            -> inbox 'Punto no existe en sistema' (origen M), sin request
    - punto OK + transferencia      -> inbox 'Creación en espera' (M)
    - punto OK + sin transferencia  -> inbox 'S/N no encontrado' (M)
  S/N encontrado:
    - punto inexistente            -> inbox 'Punto no existe' (M) + continue, sin request
    - ubicación False              -> inbox 'Sin evento de instalación' (N) + sigue
    - ubicación distinta           -> inbox 'Cambio de ubicación' (N) + sigue
    - ubicación coincide           -> sin notificación de ubicación
    - sin solicitud activa (crear):  operativo Sí -> create stage '5' + 2 write + feedback
                                     operativo No -> create stage '3' + attachment
    - con solicitud activa (update): operativo Sí -> write stage 5 + close_date (sin create)
                                     operativo No -> write stage 3 + attachment (sin create)

Bordes NO-Odoo (user/PDF) parcheados por la fixture `patch_externals` (conftest.py).
"""

import pandas as pd
import pytest

import processor

LOC = "[Las Tórtolas] Pozo BN6"

# Tuplas que inbox() escribe según la etiqueta/origen (data_processing.inbox).
ETIQUETA = {
    "Punto no existe en sistema": [(4, 4)],
    "Creación en espera": [(4, 2)],
    "S/N no encontrado": [(4, 5)],
    "Cambio de ubicación": [(4, 3)],
    "Sin evento de instalación": [(4, 6)],
}
ORIGEN = {"A": [(4, 2)], "M": [(4, 1)], "N": [(4, 3)]}

ACC_COLS = ("OT", "Técnico", "Fecha de revisión", "Proyecto", "Punto de monitoreo",
            "Equipo/instrumento", "Modelo", "N° serie", "Tipo", "Mensaje")


def _mc_dataframe(serial="SN-1", operativo="Sí",
                  punto="Pozo BN6 [Las Tórtolas]", activo="Caudalímetro"):
    row = {
        "#": 145, "user": 42, "Fecha visita ": "2026-05-26 10:00:00",
        "Nombre del Cliente": "Cliente QA",
        "1.1 Punto de monitoreo": punto,
        "1.2 Tipo de trabajo a realizar": "MC",
        "1.3 Resolución de visita": "Visita OK",
        "1.4 Fotos recinto": ["sim://foto1"],
        "1.2.1 MC | Modelo": "Modelo-QA",
        "1.2.1 MC | Activo a intervenir": activo,
        "1.2.1 MC | N° de serie": serial,
        "1.2.1 MC | ¿Equipo operativo tras trabajos?": operativo,
        "1.2.1 MC | Observación": "obs QA",
    }
    return pd.DataFrame([row])


def _equipo(loc_name=LOC):
    return [{"id": 42, "x_studio_location": [7, loc_name] if loc_name else False}]


def _inbox(spy, field):
    return [r.get(field) for r in spy.created("x_inbox_integracion")]


def _run(spy, df):
    resumen = {k: [] for k in ACC_COLS}
    exito = {k: [] for k in ACC_COLS}
    processor.process_entrys(df, "KEY", resumen, exito, spy)
    return resumen, exito


# ---------- prueba de humo del parsing ---------- #
def test_mc_consulta_equipo_por_serial(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    _run(spy, _mc_dataframe(serial="SN-XYZ"))
    eq = spy.calls_of("search_read", "maintenance.equipment")
    assert eq and eq[0].args[0] == [["serial_no", "=", "SN-XYZ"]], spy.dump()


def test_mc_serial_float_no_se_normaliza_obs11(patch_externals, spy):  # OBS-11 (testigo)
    """Defecto conocido: un serial puramente numérico que pandas infiere como float
    (p.ej. 24000.0) se usa TAL CUAL en la búsqueda exacta `[['serial_no','=',...]]`.

    El bloque "asegurar float->int" (processor.py L340-342) corre DESPUÉS de capturar
    `serial_MC` y solo muta el dict, no la variable usada en `search_read`. Resultado:
    se busca con float 24000.0 contra un campo char "24000" -> no calza -> el equipo
    "desaparece" aunque exista, y todo el módulo cae al fallback de S/N no encontrado.

    Este test es un TESTIGO del defecto (caracterización): afirma el comportamiento
    actual. Al corregir OBS-11 (normalizar a string limpio antes del search) debe
    actualizarse para exigir `"24000"`."""
    spy.set_default("search_read", "maintenance.equipment", [])
    _run(spy, _mc_dataframe(serial=24000.0))
    eq = spy.calls_of("search_read", "maintenance.equipment")
    assert eq, spy.dump()
    valor = eq[0].args[0][0][2]  # dominio [["serial_no", "=", <valor>]]
    assert isinstance(valor, float), f"OBS-11: se esperaba float sin normalizar, fue {type(valor).__name__}"
    assert float(valor) == 24000.0
    assert not isinstance(valor, str), "OBS-11: la búsqueda NO normaliza el serial a string"


# ---------- S/N NO encontrado ---------- #
def test_mc_sn_no_encontrado_punto_inexistente(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    spy.set_default("search_read", "x_maintenance_location", [])  # punto no existe
    _run(spy, _mc_dataframe(serial="SN-404"))
    assert spy.created("maintenance.request") == []
    assert ETIQUETA["Punto no existe en sistema"] in _inbox(spy, "x_studio_etiqueta")
    assert ORIGEN["M"] in _inbox(spy, "x_studio_origen")


def test_mc_sn_no_encontrado_con_transferencia(patch_externals, spy):  # Creación en espera
    spy.set_default("search_read", "maintenance.equipment", [])
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    spy.set_default("search_read", "stock.move.line", [{"id": 1}])  # transferencia pendiente
    _run(spy, _mc_dataframe(serial="SN-TRANSIT"))
    assert spy.created("maintenance.request") == []
    assert ETIQUETA["Creación en espera"] in _inbox(spy, "x_studio_etiqueta")


def test_mc_sn_no_encontrado_sin_transferencia(patch_externals, spy):  # S/N no encontrado
    spy.set_default("search_read", "maintenance.equipment", [])
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    spy.set_default("search_read", "stock.move.line", [])  # sin movimiento
    _run(spy, _mc_dataframe(serial="SN-404"))
    assert spy.created("maintenance.request") == []
    assert ETIQUETA["S/N no encontrado"] in _inbox(spy, "x_studio_etiqueta")


# ---------- S/N encontrado: validaciones de punto / ubicación ---------- #
def test_mc_equipo_ok_punto_inexistente(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo())
    spy.set_default("search_read", "x_maintenance_location", [])  # ningún punto matchea
    _run(spy, _mc_dataframe())
    assert spy.created("maintenance.request") == []
    assert ETIQUETA["Punto no existe en sistema"] in _inbox(spy, "x_studio_etiqueta")
    # punto se valida ANTES que ubicación → no debe notificar ubicación
    assert spy.calls_of("message_post", "maintenance.equipment") == []


def test_mc_equipo_sin_ubicacion_notifica_y_continua(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo(loc_name=False))
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    _run(spy, _mc_dataframe(operativo="Sí"))
    assert ETIQUETA["Sin evento de instalación"] in _inbox(spy, "x_studio_etiqueta")
    assert ORIGEN["N"] in _inbox(spy, "x_studio_origen")
    assert spy.calls_of("message_post", "maintenance.equipment"), "debió notificar sin-evento"
    assert spy.created("maintenance.request"), "tras notificar debe seguir y crear la solicitud"


def test_mc_equipo_cambio_de_ubicacion_notifica_y_continua(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo(loc_name="[Otro] Punto X"))
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    _run(spy, _mc_dataframe(operativo="Sí"))
    assert ETIQUETA["Cambio de ubicación"] in _inbox(spy, "x_studio_etiqueta")
    assert spy.created("maintenance.request"), "tras notificar cambio debe seguir y crear"


def test_mc_ubicacion_coincide_no_notifica(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo())  # loc == punto
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    _run(spy, _mc_dataframe(operativo="Sí"))
    assert spy.calls_of("message_post", "maintenance.equipment") == []


# ---------- Crear (sin solicitud activa) ---------- #
def test_mc_crear_operativo_si(patch_externals, spy):  # TC-MC-03
    spy.set_default("search_read", "maintenance.equipment", _equipo())
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    # search('maintenance.request') -> [] por defecto => interruptor=True (crear)
    _run(spy, _mc_dataframe(operativo="Sí"))
    creates = spy.created("maintenance.request")
    assert creates, spy.dump()
    v = creates[0]
    assert v.get("stage_id") == "5"
    assert v.get("equipment_id") == 42
    assert v.get("x_studio_tipo_de_trabajo") == "Mantención Correctiva"
    writes = spy.writes("maintenance.request")
    assert any(w.get("stage_id") == 5 for _, w in writes)
    assert any(w.get("x_studio_tcnico") == 145 and "close_date" in w for _, w in writes)


def test_mc_crear_operativo_no(patch_externals, spy):  # TC-MC-04
    spy.set_default("search_read", "maintenance.equipment", _equipo())
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    _run(spy, _mc_dataframe(operativo="No"))
    creates = spy.created("maintenance.request")
    assert creates and creates[0].get("stage_id") == "3", spy.dump()
    assert spy.created("ir.attachment"), "operativo=No adjunta el PDF"


# ---------- Actualizar (con solicitud activa) ---------- #
def _equipo_con_request_activa(spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo())
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    spy.set_default("search", "maintenance.request", [101])     # hay una solicitud
    # read de esa solicitud: con fecha y NO finalizada/desechada => interruptor=False
    spy.set_default("read", "maintenance.request",
                    [{"schedule_date": "2026-05-20", "stage_id": [3, "En proceso"], "name": "OT"}])


def test_mc_actualizar_operativo_si(patch_externals, spy):  # TC-MC-01
    _equipo_con_request_activa(spy)
    _run(spy, _mc_dataframe(operativo="Sí"))
    assert spy.created("maintenance.request") == [], "no debe crear: hay solicitud activa"
    writes = spy.writes("maintenance.request")
    assert any(ids == [101] and w.get("stage_id") == 5 for ids, w in writes), spy.dump()
    assert any(ids == [101] and "close_date" in w for ids, w in writes)


def test_mc_actualizar_operativo_no(patch_externals, spy):  # TC-MC-02
    _equipo_con_request_activa(spy)
    _run(spy, _mc_dataframe(operativo="No"))
    assert spy.created("maintenance.request") == []
    writes = spy.writes("maintenance.request")
    assert any(ids == [101] and w.get("stage_id") == 3 for ids, w in writes), spy.dump()
    assert spy.created("ir.attachment")
