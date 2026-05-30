"""L2 · Componente — process_entrys, módulo CF (Configuración), todas las ramas.

CF comparte el pipeline de validación con MC (S/N, ubicación, punto) y agrega
selección por proximidad temporal + archivado (processor.py L947-1631):

  S/N NO encontrado:  punto inexistente / con transferencia / sin transferencia
  S/N encontrado:
    crear (sin solicitudes de interés):  operativo Sí -> create stage '5'
                                         operativo No -> create stage '3' + attachment
    seleccionar existente:
      hay una en stage=3                 -> usar esa (write 5), sin archivar
      varias, ninguna en proceso         -> la más cercana (write 5) + archivar anteriores
"""

import pandas as pd

import processor

LOC = "[Las Tórtolas] Pozo BN6"
ETIQUETA = {"Punto no existe en sistema": [(4, 4)], "Creación en espera": [(4, 2)],
            "S/N no encontrado": [(4, 5)], "Cambio de ubicación": [(4, 3)],
            "Sin evento de instalación": [(4, 6)]}
ACC_COLS = ("OT", "Técnico", "Fecha de revisión", "Proyecto", "Punto de monitoreo",
            "Equipo/instrumento", "Modelo", "N° serie", "Tipo", "Mensaje")


def _cf_df(serial="SN-CF", operativo="Sí", punto="Pozo BN6 [Las Tórtolas]"):
    row = {
        "#": 300, "user": 42, "Fecha visita ": "2026-05-26 10:00:00",
        "Nombre del Cliente": "Cliente QA",
        "1.1 Punto de monitoreo": punto,
        "1.2 Tipo de trabajo a realizar": "CF",
        "1.3 Resolución de visita": "Visita OK",
        "1.4 Fotos recinto": ["sim://foto1"],
        "1.2.1 CF | Modelo": "Modelo-QA",
        "1.2.1 CF | Activo a intervenir": "Caudalímetro",
        "1.2.1 CF | N° de serie": serial,
        "1.2.1 CF | ¿Equipo operativo tras trabajos?": operativo,
        "1.2.1 CF | Observación": "obs QA",
        "1.2.1 CF | Tipo de Ajuste": "Ajuste de fábrica",
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


# ---------- S/N NO encontrado ---------- #
def test_cf_sn_punto_inexistente(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    spy.set_default("search_read", "x_maintenance_location", [])
    _run(spy, _cf_df(serial="SN-404"))
    assert spy.created("maintenance.request") == []
    assert ETIQUETA["Punto no existe en sistema"] in _inbox(spy, "x_studio_etiqueta")


def test_cf_sn_con_transferencia(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    spy.set_default("search_read", "stock.move.line", [{"id": 1}])
    _run(spy, _cf_df(serial="SN-T"))
    assert ETIQUETA["Creación en espera"] in _inbox(spy, "x_studio_etiqueta")


def test_cf_sn_sin_transferencia(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    spy.set_default("search_read", "stock.move.line", [])
    _run(spy, _cf_df(serial="SN-404"))
    assert ETIQUETA["S/N no encontrado"] in _inbox(spy, "x_studio_etiqueta")


# ---------- validaciones de equipo encontrado ---------- #
def test_cf_equipo_sin_ubicacion(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo(loc_name=False))
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    _run(spy, _cf_df())
    assert ETIQUETA["Sin evento de instalación"] in _inbox(spy, "x_studio_etiqueta")


def test_cf_equipo_cambio_ubicacion(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo(loc_name="[Otro] X"))
    spy.set_default("search_read", "x_maintenance_location", [{"id": 99, "x_name": LOC}])
    _run(spy, _cf_df())
    assert ETIQUETA["Cambio de ubicación"] in _inbox(spy, "x_studio_etiqueta")


# ---------- crear (sin solicitudes) ---------- #
def test_cf_crear_operativo_si(patch_externals, spy):
    _equipo_ok(spy)
    _run(spy, _cf_df(operativo="Sí"))
    creates = spy.created("maintenance.request")
    assert creates, spy.dump()
    assert creates[0].get("stage_id") == "5"
    assert creates[0].get("x_studio_tipo_de_trabajo") == "Configuración"


def test_cf_crear_operativo_no(patch_externals, spy):
    _equipo_ok(spy)
    _run(spy, _cf_df(operativo="No"))
    creates = spy.created("maintenance.request")
    assert creates and creates[0].get("stage_id") == "3"
    assert spy.created("ir.attachment")


# ---------- seleccionar existente: stage=3 prioritario ---------- #
def test_cf_usa_solicitud_en_proceso_sin_archivar(patch_externals, spy):
    _equipo_ok(spy)
    spy.set_default("search", "maintenance.request", [301])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-05-01", "stage_id": [3, "En proceso"],
                "name": "OT", "archive": False}])
    _run(spy, _cf_df(operativo="Sí"))
    assert spy.created("maintenance.request") == [], "no debe crear si hay activa"
    writes = spy.writes("maintenance.request")
    assert any(ids == [301] and w.get("stage_id") == 5 for ids, w in writes), spy.dump()
    assert not any(w.get("archive") for _, w in writes), "una sola activa: no archiva"


# ---------- seleccionar existente: proximidad + archivado ---------- #
def test_cf_proximidad_archiva_anterior(patch_externals, spy):
    _equipo_ok(spy)
    spy.set_default("search", "maintenance.request", [201, 202])
    # read por id (FIFO en el orden del search): 201 más antigua, 202 más cercana a 2026-05-26
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-04-01", "stage_id": [2, "Nuevo"], "name": "vieja", "archive": False}])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-05-25", "stage_id": [2, "Nuevo"], "name": "nueva", "archive": False}])
    _run(spy, _cf_df(operativo="Sí"))
    assert spy.created("maintenance.request") == []
    writes = spy.writes("maintenance.request")
    # archiva la 201 (anterior a la elegida 202)
    assert any(ids == [201] and w.get("archive") is True for ids, w in writes), spy.dump()
    # finaliza la 202 (la más cercana)
    assert any(ids == [202] and w.get("stage_id") == 5 for ids, w in writes), spy.dump()


# ---------- el archivado por proximidad cierra la mail.activity ---------- #
def test_cf_archivado_cierra_actividad(patch_externals, spy):
    """QA detectó que las archivadas por proximidad dejaban su mail.activity abierta."""
    _equipo_ok(spy)
    spy.set_default("search", "maintenance.request", [201, 202])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-04-01", "stage_id": [2, "Nuevo"], "name": "vieja", "archive": False}])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-05-25", "stage_id": [2, "Nuevo"], "name": "nueva", "archive": False}])
    spy.set_default("search_read", "mail.activity", [{"id": 777}])
    _run(spy, _cf_df(operativo="Sí"))
    # archiva la 201
    assert any(ids == [201] and w.get("archive") is True
               for ids, w in spy.writes("maintenance.request")), spy.dump()
    # y le da fin a la actividad asociada
    feedbacks = spy.calls_of("action_feedback", "mail.activity")
    assert any(c.args[0] == [777] for c in feedbacks), spy.dump()


# ---------- la actualización por proximidad escribe el técnico ---------- #
def test_cf_proximidad_actualiza_tecnico_operativo_si(patch_externals, spy):
    _equipo_ok(spy)
    spy.set_default("search", "maintenance.request", [201, 202])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-04-01", "stage_id": [2, "Nuevo"], "name": "vieja", "archive": False}])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-05-25", "stage_id": [2, "Nuevo"], "name": "nueva", "archive": False}])
    _run(spy, _cf_df(operativo="Sí"))
    # 145 = id de "Diego Marchant" en processor.operators (técnico del fixture patch_externals)
    assert any(ids == [202] and w.get("x_studio_tcnico") == 145
               for ids, w in spy.writes("maintenance.request")), spy.dump()


def test_cf_proximidad_actualiza_tecnico_operativo_no(patch_externals, spy):
    _equipo_ok(spy)
    spy.set_default("search", "maintenance.request", [201, 202])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-04-01", "stage_id": [2, "Nuevo"], "name": "vieja", "archive": False}])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-05-25", "stage_id": [2, "Nuevo"], "name": "nueva", "archive": False}])
    _run(spy, _cf_df(operativo="No"))
    assert any(ids == [202] and w.get("x_studio_tcnico") == 145
               for ids, w in spy.writes("maintenance.request")), spy.dump()
