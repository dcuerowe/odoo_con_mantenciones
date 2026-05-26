"""L2 · Componente — process_entrys, módulo I (Instalación), TODAS las ramas.

I es el módulo que ESCRIBE x_studio_location del equipo y selecciona la PRIMERA
solicitud activa (no por proximidad). processor.py L3004-3605.

  punto inexistente            -> inbox 'Punto no existe' + continue
  ubicación False              -> write x_studio_location = punto (sin inbox de cambio)
  ubicación distinta           -> write ubicación + inbox 'Cambio de ubicación'
  ubicación coincide           -> no escribe ubicación
  crear (sin activas):  operativo Sí -> create '5' + 2 write ; No -> create '3' + attachment
  actualizar (primera activa):  operativo Sí -> write 5 ; No -> attachment (sin cambiar stage)
"""

import pandas as pd

import processor

LOC = "[Las Tórtolas] Pozo BN6"
PUNTO_ID = 99
ETIQUETA = {"Punto no existe en sistema": [(4, 4)], "Cambio de ubicación": [(4, 3)]}
ACC_COLS = ("OT", "Técnico", "Fecha de revisión", "Proyecto", "Punto de monitoreo",
            "Equipo/instrumento", "Modelo", "N° serie", "Tipo", "Mensaje")


def _i_df(serial="SN-I", operativo="Sí", punto="Pozo BN6 [Las Tórtolas]"):
    row = {
        "#": 400, "user": 42, "Fecha visita ": "2026-05-26 10:00:00",
        "Nombre del Cliente": "Cliente QA",
        "1.1 Punto de monitoreo": punto,
        "1.2 Tipo de trabajo a realizar": "I",
        "1.3 Resolución de visita": "Visita OK",
        "1.4 Fotos recinto": ["sim://foto1"],
        "1.2.1 I (I) | Modelo": "Modelo-QA",
        "1.2.1 I (I) | Tipo de dispositivo": "Caudalímetro",
        "1.2.1 I (I) | N° de serie": serial,
        "1.2.1 I (I) | ¿Equipo operativo tras trabajos?": operativo,
        "1.2.1 I (I) | Observación": "obs QA",
    }
    return pd.DataFrame([row])


def _equipo(loc_name=LOC):
    return [{"id": 42, "x_studio_location": [7, loc_name] if loc_name else False}]


def _inbox(spy, field):
    return [r.get(field) for r in spy.created("x_inbox_integracion")]


def _eq_loc_writes(spy):
    return [w for _, w in spy.writes("maintenance.equipment") if "x_studio_location" in w]


def _run(spy, df):
    r = {k: [] for k in ACC_COLS}
    e = {k: [] for k in ACC_COLS}
    processor.process_entrys(df, "KEY", r, e, spy)
    return r, e


def _punto_ok(spy):
    spy.set_default("search_read", "x_maintenance_location", [{"id": PUNTO_ID, "x_name": LOC}])


# ---------- validaciones ---------- #
def test_i_punto_inexistente(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo())
    spy.set_default("search_read", "x_maintenance_location", [])
    _run(spy, _i_df())
    assert spy.created("maintenance.request") == []
    assert ETIQUETA["Punto no existe en sistema"] in _inbox(spy, "x_studio_etiqueta")


def test_i_sn_no_encontrado_no_crea(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    _run(spy, _i_df(serial="SN-404"))
    assert spy.created("maintenance.request") == []


# ---------- movimiento de ubicación ---------- #
def test_i_ubicacion_false_escribe_punto(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo(loc_name=False))
    _punto_ok(spy)
    _run(spy, _i_df(operativo="Sí"))
    locs = _eq_loc_writes(spy)
    assert locs and locs[0]["x_studio_location"] == PUNTO_ID, spy.dump()
    # sin ubicación previa => NO es "cambio de ubicación"
    assert ETIQUETA["Cambio de ubicación"] not in _inbox(spy, "x_studio_etiqueta")


def test_i_ubicacion_distinta_mueve_y_notifica(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo(loc_name="[Otro] Punto X"))
    _punto_ok(spy)
    _run(spy, _i_df(operativo="Sí"))
    locs = _eq_loc_writes(spy)
    assert locs and locs[0]["x_studio_location"] == PUNTO_ID
    assert ETIQUETA["Cambio de ubicación"] in _inbox(spy, "x_studio_etiqueta")


def test_i_ubicacion_coincide_no_mueve(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo())  # loc == punto
    _punto_ok(spy)
    _run(spy, _i_df(operativo="Sí"))
    assert _eq_loc_writes(spy) == [], "ubicación coincide: no debe reescribir x_studio_location"


# ---------- crear ---------- #
def test_i_crear_operativo_si(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo())
    _punto_ok(spy)
    _run(spy, _i_df(operativo="Sí"))
    creates = spy.created("maintenance.request")
    assert creates and creates[0].get("stage_id") == "5", spy.dump()
    assert creates[0].get("x_studio_tipo_de_trabajo") == "Instalación"


def test_i_crear_operativo_no(patch_externals, spy):
    """I crear-operativo-No: crea el request (stage '3'), registra el éxito y adjunta
    el PDF. Verifica la corrección de OBS-10 (antes `created_request_I` no asignado en
    L3471 lanzaba NameError y perdía el éxito/adjunto; ahora usa `created_request_II`)."""
    spy.set_default("search_read", "maintenance.equipment", _equipo())
    _punto_ok(spy)
    resumen, exito = _run(spy, _i_df(operativo="No"))
    creates = spy.created("maintenance.request")
    assert creates and creates[0].get("stage_id") == "3", spy.dump()
    # OBS-10 corregido: ahora SÍ se registra el éxito y se adjunta el PDF.
    assert any("instalación" in m.lower() for m in exito["Mensaje"]), \
        f"debe registrar el éxito de la instalación; exito={exito['Mensaje']}"
    assert spy.created("ir.attachment"), "operativo=No debe adjuntar el PDF a la solicitud"


# ---------- actualizar: PRIMERA activa (no proximidad) ---------- #
def test_i_actualiza_la_primera_activa(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo())
    _punto_ok(spy)
    spy.set_default("search", "maintenance.request", [501, 502])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-05-01", "stage_id": [2, "Nuevo"], "name": "a", "archive": False}])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-04-01", "stage_id": [2, "Nuevo"], "name": "b", "archive": False}])
    _run(spy, _i_df(operativo="Sí"))
    assert spy.created("maintenance.request") == [], "no crea: hay activas"
    writes = spy.writes("maintenance.request")
    # toma la PRIMERA del search (501), no la más cercana en fecha (502)
    assert any(ids == [501] and w.get("stage_id") == 5 for ids, w in writes), spy.dump()
    assert not any(ids == [502] and w.get("stage_id") == 5 for ids, w in writes)


def test_i_actualiza_operativo_no_adjunta(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo())
    _punto_ok(spy)
    spy.set_default("search", "maintenance.request", [501])
    spy.queue("read", "maintenance.request",
              [{"schedule_date": "2026-05-01", "stage_id": [3, "En proceso"], "name": "a", "archive": False}])
    _run(spy, _i_df(operativo="No"))
    assert spy.created("maintenance.request") == []
    assert spy.created("ir.attachment"), "operativo=No adjunta PDF a la solicitud existente"
