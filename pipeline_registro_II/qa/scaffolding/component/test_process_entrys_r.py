"""L2 · Componente — process_entrys, módulo R (Reemplazo/Extracción), ramas principales.

R es bifásico: alcance (Calibración vs daño) × subtrabajo (E saliente / I entrante) ×
destino. Itera el par (E, I) en una sola submission. processor.py L1691-2913.
Ubicaciones: 593 = Laboratorio, 594 = Bodega cliente, id_punto = punto del formulario.
Punto '1' a propósito (el '3' tiene un hack que lo omite, L1698).
"""

import pandas as pd

import processor

LOC = "[Las Tórtolas] Pozo BN6"
PUNTO_ID = 99
ETIQUETA = {"Punto no existe en sistema": [(4, 4)]}
ACC_COLS = ("OT", "Técnico", "Fecha de revisión", "Proyecto", "Punto de monitoreo",
            "Equipo/instrumento", "Modelo", "N° serie", "Tipo", "Mensaje")


def _r_df(motivo="Otro", destino="Bodega cliente", punto="Pozo BN6 [Las Tórtolas]"):
    row = {
        "#": 236, "user": 42, "Fecha visita ": "2026-05-26 10:00:00",
        "Nombre del Cliente": "Cliente QA",
        "1.1 Punto de monitoreo": punto,
        "1.2 Tipo de trabajo a realizar": "R",
        "1.3 Resolución de visita": "Visita OK",
        "1.4 Fotos recinto": ["sim://foto1"],
        "1.2.1 R | Tipo equipo/instrumento a reemplazar": "Caudalímetro",
        "1.2.1 R | Observación": "obs QA",
        "1.2.1 R | Motivo de reemplazo": motivo,
        "1.2.1 R (E) | Modelo": "Modelo-E",
        "1.2.1 R (E) | N° de serie": "SN-E",
        "1.2.1 R (E) | Destino": destino,
        "1.2.1 R (I) | Modelo": "Modelo-I",
        "1.2.1 R (I) | N° de serie": "SN-I",
    }
    return pd.DataFrame([row])


def _equipo():
    return [{"id": 42, "x_studio_location": [7, LOC]}]


def _inbox(spy, field):
    return [r.get(field) for r in spy.created("x_inbox_integracion")]


def _tipos(spy):
    return {c.get("x_studio_tipo_de_trabajo") for c in spy.created("maintenance.request")}


def _loc_writes(spy):
    return [w.get("x_studio_location") for _, w in spy.writes("maintenance.equipment")
            if "x_studio_location" in w]


def _run(spy, df):
    r = {k: [] for k in ACC_COLS}
    e = {k: [] for k in ACC_COLS}
    processor.process_entrys(df, "KEY", r, e, spy)
    return r, e


def _equipo_ok(spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo())
    spy.set_default("search_read", "x_maintenance_location", [{"id": PUNTO_ID, "x_name": LOC}])
    spy.set_default("search_read", "mail.activity", [{"id": 555}])


# ---------- parsing / S/N ---------- #
def test_r_consulta_equipo_por_serial_e_y_i(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    _run(spy, _r_df())
    dominios = [c.args[0] for c in spy.calls_of("search_read", "maintenance.equipment")]
    assert [["serial_no", "=", "SN-E"]] in dominios
    assert [["serial_no", "=", "SN-I"]] in dominios


def test_r_sn_no_encontrado_no_crea(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    _run(spy, _r_df())
    assert spy.created("maintenance.request") == []


def test_r_punto_inexistente(patch_externals, spy):
    spy.set_default("search_read", "maintenance.equipment", _equipo())
    spy.set_default("search_read", "x_maintenance_location", [])  # punto no existe
    _run(spy, _r_df())
    assert spy.created("maintenance.request") == []
    assert ETIQUETA["Punto no existe en sistema"] in _inbox(spy, "x_studio_etiqueta")


# ---------- flujo de daño (Otro motivo) ---------- #
def test_r_dano_crea_extraccion_e_instalacion(patch_externals, spy):
    _equipo_ok(spy)
    _run(spy, _r_df(motivo="Otro", destino="Bodega cliente"))
    tipos = _tipos(spy)
    assert "Extracción" in tipos and "Instalación" in tipos, f"tipos={tipos}\n{spy.dump()}"


# ---------- flujo de calibración ---------- #
def test_r_calibracion_lab_mueve_a_593(patch_externals, spy):
    _equipo_ok(spy)
    _run(spy, _r_df(motivo="Ciclo de calibración", destino="Laboratorio | Metrocal"))
    tipos = _tipos(spy)
    assert "Extracción" in tipos, f"tipos={tipos}\n{spy.dump()}"
    assert "Calibración" in tipos, f"tipos={tipos}\n{spy.dump()}"
    assert "Instalación" in tipos, f"tipos={tipos}\n{spy.dump()}"
    locs = _loc_writes(spy)
    assert 593 in locs, f"el saliente debía moverse a 593 (Laboratorio); locs={locs}"
    assert PUNTO_ID in locs, f"el entrante debía moverse al punto {PUNTO_ID}; locs={locs}"


def test_r_calibracion_bodega_mueve_a_594(patch_externals, spy):
    _equipo_ok(spy)
    _run(spy, _r_df(motivo="Ciclo de calibración", destino="Bodega cliente"))
    locs = _loc_writes(spy)
    assert 594 in locs, f"el saliente debía moverse a 594 (Bodega); locs={locs}\n{spy.dump()}"


# ---------- sub-flujo I con calibración activa preexistente (bug OT 270) ---------- #
def _calibracion_activa(spy, activity=None):
    """Escenario de la OT 270: el equipo entrante ya tiene una request de
    Calibración 'En proceso' (id 1822). destino='Bodega cliente' para que la fase E
    NO consulte maintenance.request y el único `search` lo haga la fase I."""
    _equipo_ok(spy)
    spy.set_default("search", "maintenance.request", [1822])
    spy.set_default("read", "maintenance.request",
                    [{"schedule_date": "2026-05-20", "stage_id": [3, "En proceso"],
                      "name": "Calibración OT", "archive": False}])
    spy.set_default("search_read", "mail.activity",
                    [{"id": 777}] if activity is None else activity)


def test_r_calibracion_instalacion_cierra_actividad_y_crea(patch_externals, spy):
    """Regresión del UnboundLocalError 'created_request_CI' en la rama I.
    Con una calibración activa (1822), la fase I debe: finalizarla (stage 5),
    cerrar SU actividad (buscada por res_id == id_CI, no la variable inexistente)
    y crear la request de Instalación."""
    _calibracion_activa(spy)
    _run(spy, _r_df(motivo="Ciclo de calibración", destino="Bodega cliente"))

    # 1. La actividad se busca por la calibración existente (id_CI = 1822), no por
    #    'created_request_CI' (que no existe en esta rama y causaba el crash).
    dominios_act = [c.args[0] for c in spy.calls_of("search_read", "mail.activity")]
    assert any(["res_id", "=", 1822] in dom for dom in dominios_act), \
        f"debe buscar la actividad de la calibración 1822; dominios={dominios_act}\n{spy.dump()}"

    # 2. La calibración 1822 se finaliza (stage 5).
    assert any(ids == [1822] and w.get("stage_id") == 5
               for ids, w in spy.writes("maintenance.request")), spy.dump()

    # 3. La actividad se cierra y la Instalación SÍ se crea (antes el crash + continue
    #    abortaba la iteración antes de llegar a la creación).
    assert spy.calls_of("action_feedback", "mail.activity"), "debió cerrar la actividad"
    assert "Instalación" in _tipos(spy), f"tipos={_tipos(spy)}\n{spy.dump()}"


def test_r_instalacion_se_crea_aunque_falte_actividad(patch_externals, spy):
    """Endurecimiento: si la actividad de la calibración no existe (o falla su
    cierre), la creación de la Instalación NO debe abortarse (se quitaron los
    'continue' del manejo de actividad)."""
    _calibracion_activa(spy, activity=[])  # no hay actividad que cerrar
    _run(spy, _r_df(motivo="Ciclo de calibración", destino="Bodega cliente"))

    assert any(ids == [1822] and w.get("stage_id") == 5
               for ids, w in spy.writes("maintenance.request")), spy.dump()
    assert "Instalación" in _tipos(spy), \
        f"la Instalación debe crearse aunque no haya actividad; tipos={_tipos(spy)}\n{spy.dump()}"


# ---------- R agrega followers 5205 y 172 a sus solicitudes ---------- #
def test_r_followers(patch_externals, spy):
    _equipo_ok(spy)
    _run(spy, _r_df(motivo="Otro", destino="Bodega cliente"))
    subs = [args[1] for args in
            [c.args for c in spy.calls_of("message_subscribe", "maintenance.request")]]
    assert subs, "R debe suscribir followers a las solicitudes"
    assert all(5205 in s and 172 in s for s in subs), f"followers R inesperados: {subs}"
