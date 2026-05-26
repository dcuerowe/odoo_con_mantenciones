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


# ---------- R agrega followers 5205 y 172 a sus solicitudes ---------- #
def test_r_followers(patch_externals, spy):
    _equipo_ok(spy)
    _run(spy, _r_df(motivo="Otro", destino="Bodega cliente"))
    subs = [args[1] for args in
            [c.args for c in spy.calls_of("message_subscribe", "maintenance.request")]]
    assert subs, "R debe suscribir followers a las solicitudes"
    assert all(5205 in s and 172 in s for s in subs), f"followers R inesperados: {subs}"
