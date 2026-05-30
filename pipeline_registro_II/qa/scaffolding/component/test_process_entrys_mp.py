"""L2 · Componente — process_entrys, módulo MP (Mantención Preventiva), TODAS las ramas.

MP comparte el pipeline de validación y la selección por proximidad+archivado de CF,
y agrega el registro 'Equipo sin plan de mantenimiento' al crear. processor.py L3725-4345.
"""

import pandas as pd

import processor

LOC = "[Las Tórtolas] Pozo BN6"
ETIQUETA = {"Punto no existe en sistema": [(4, 4)], "Creación en espera": [(4, 2)],
            "S/N no encontrado": [(4, 5)], "Sin evento de instalación": [(4, 6)],
            "Cambio de ubicación": [(4, 3)]}
ACC_COLS = ("OT", "Técnico", "Fecha de revisión", "Proyecto", "Punto de monitoreo",
            "Equipo/instrumento", "Modelo", "N° serie", "Tipo", "Mensaje")


def _mp_df(serial="SN-MP", operativo="Sí", punto="Pozo BN6 [Las Tórtolas]"):
    row = {
        "#": 500, "user": 42, "Fecha visita ": "2026-05-26 10:00:00",
        "Nombre del Cliente": "Cliente QA",
        "1.1 Punto de monitoreo": punto,
        "1.2 Tipo de trabajo a realizar": "MP",
        "1.3 Resolución de visita": "Visita OK",
        "1.4 Fotos recinto": ["sim://foto1"],
        "1.2.1 MP (I) | Modelo": "Modelo-QA",
        "1.2.1 MP (I) | Dispositivo a intervenir": "Caudalímetro",
        "1.2.1 MP (I) | N° de serie": serial,
        "1.2.1 MP (I) | ¿Dispositivo operativo tras trabajos?": operativo,
        "1.2.1 MP (I) | Observación": "obs QA",
    }
    return pd.DataFrame([row])


def _equipo(loc_name=LOC):
    return [{"id": 42, "x_studio_location": [7, loc_name] if loc_name else False}]


def _inbox(spy, field):
    return [r.get(field) for r in spy.created("x_inbox_integracion")]


def _run(spy, df):
    r = {k: [] for k in ACC_COLS}
    e = {k: [] for k in ACC_COLS}
    processor.process_entrys(df, "KEY", r, e, spy)
    return r, e


def _equipo_ok(spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo())
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    # mail.activity presente => el feedback no aborta (evita el continue de L4223)
    spy.set_default("search_read", "mail.activity", [{"id": 555}])


# ---------- S/N NO encontrado ---------- #
def test_mp_sn_punto_inexistente(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    spy.set_default("search_read", "x_maintenance_location", [])
    _run(spy, _mp_df(serial="SN-404"))
    assert spy.created("maintenance.request") == []
    assert ETIQUETA["Punto no existe en sistema"] in _inbox(spy, "x_studio_etiqueta")


def test_mp_sn_con_transferencia(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    spy.set_default("search_read", "stock.move.line", [{"id": 1}])
    _run(spy, _mp_df(serial="SN-T"))
    assert ETIQUETA["Creación en espera"] in _inbox(spy, "x_studio_etiqueta")


def test_mp_sn_sin_transferencia(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    spy.set_default("search_read", "stock.move.line", [])
    _run(spy, _mp_df(serial="SN-404"))
    assert ETIQUETA["S/N no encontrado"] in _inbox(spy, "x_studio_etiqueta")


# ---------- validaciones de equipo encontrado ---------- #
def test_mp_equipo_sin_ubicacion(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo(loc_name=False))
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    spy.set_default("search_read", "mail.activity", [{"id": 555}])
    _run(spy, _mp_df())
    assert ETIQUETA["Sin evento de instalación"] in _inbox(spy, "x_studio_etiqueta")


def test_mp_equipo_cambio_ubicacion(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo(loc_name="[Otro] X"))
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    spy.set_default("search_read", "mail.activity", [{"id": 555}])
    _run(spy, _mp_df())
    assert ETIQUETA["Cambio de ubicación"] in _inbox(spy, "x_studio_etiqueta")


# ---------- crear (sin solicitudes) ---------- #
def test_mp_crear_operativo_si_y_registra_sin_plan(patch_externals, spy):
    _equipo_ok(spy)
    resumen, exito = _run(spy, _mp_df(operativo="Sí"))
    creates = spy.created("maintenance.request")
    assert creates and creates[0].get("stage_id") == "5"
    assert creates[0].get("x_studio_tipo_de_trabajo") == "Mantención Preventiva"
    mensajes = " ".join(resumen.get("Mensaje", [])).lower()
    assert "sin plan de mantenimien" in mensajes, f"resumen={resumen}"


def test_mp_crear_operativo_no(patch_externals, spy):
    _equipo_ok(spy)
    _run(spy, _mp_df(operativo="No"))
    creates = spy.created("maintenance.request")
    assert creates and creates[0].get("stage_id") == "3", spy.dump()
    assert spy.created("ir.attachment")


# ---------- seleccionar existente ---------- #
def test_mp_usa_solicitud_en_proceso(patch_externals, spy):
    _equipo_ok(spy)
    spy.set_default("search", "maintenance.request", [301])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-05-01", "stage_id": [3, "En proceso"],
                "name": "OT", "archive": False}])
    _run(spy, _mp_df(operativo="Sí"))
    assert spy.created("maintenance.request") == []
    writes = spy.writes("maintenance.request")
    assert any(ids == [301] and w.get("stage_id") == 5 for ids, w in writes), spy.dump()
    assert not any(w.get("archive") for _, w in writes)


def test_mp_proximidad_archiva_anterior(patch_externals, spy):
    _equipo_ok(spy)
    spy.set_default("search", "maintenance.request", [201, 202])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-04-01", "stage_id": [2, "Nuevo"], "name": "vieja", "archive": False}])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-05-25", "stage_id": [2, "Nuevo"], "name": "nueva", "archive": False}])
    _run(spy, _mp_df(operativo="Sí"))
    assert spy.created("maintenance.request") == []
    writes = spy.writes("maintenance.request")
    assert any(ids == [201] and w.get("archive") is True for ids, w in writes), spy.dump()
    assert any(ids == [202] and w.get("stage_id") == 5 for ids, w in writes), spy.dump()


# ---------- el archivado por proximidad cierra la mail.activity ---------- #
def test_mp_archivado_cierra_actividad(patch_externals, spy):
    """QA detectó que las archivadas por proximidad dejaban su mail.activity abierta."""
    _equipo_ok(spy)
    spy.set_default("search", "maintenance.request", [201, 202])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-04-01", "stage_id": [2, "Nuevo"], "name": "vieja", "archive": False}])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-05-25", "stage_id": [2, "Nuevo"], "name": "nueva", "archive": False}])
    spy.set_default("search_read", "mail.activity", [{"id": 888}])
    _run(spy, _mp_df(operativo="Sí"))
    assert any(ids == [201] and w.get("archive") is True
               for ids, w in spy.writes("maintenance.request")), spy.dump()
    feedbacks = spy.calls_of("action_feedback", "mail.activity")
    assert any(c.args[0] == [888] for c in feedbacks), spy.dump()


# ---------- la actualización por proximidad escribe el técnico ---------- #
def test_mp_proximidad_actualiza_tecnico_operativo_si(patch_externals, spy):
    _equipo_ok(spy)
    spy.set_default("search", "maintenance.request", [201, 202])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-04-01", "stage_id": [2, "Nuevo"], "name": "vieja", "archive": False}])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-05-25", "stage_id": [2, "Nuevo"], "name": "nueva", "archive": False}])
    _run(spy, _mp_df(operativo="Sí"))
    # 145 = id de "Diego Marchant" en processor.operators (técnico del fixture patch_externals)
    assert any(ids == [202] and w.get("x_studio_tcnico") == 145
               for ids, w in spy.writes("maintenance.request")), spy.dump()


def test_mp_proximidad_actualiza_tecnico_operativo_no(patch_externals, spy):
    _equipo_ok(spy)
    spy.set_default("search", "maintenance.request", [201, 202])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-04-01", "stage_id": [2, "Nuevo"], "name": "vieja", "archive": False}])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-05-25", "stage_id": [2, "Nuevo"], "name": "nueva", "archive": False}])
    _run(spy, _mp_df(operativo="No"))
    assert any(ids == [202] and w.get("x_studio_tcnico") == 145
               for ids, w in spy.writes("maintenance.request")), spy.dump()
