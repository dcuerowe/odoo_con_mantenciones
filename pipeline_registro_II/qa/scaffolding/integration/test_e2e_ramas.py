"""L3 · E2E de ESCRITURA — ramas adicionales contra el test-Odoo (staging).

Cubre lo que antes solo estaba en el spy (L2), ahora verificado en Odoo real:
  - Enrutamiento de excepciones al inbox (S/N no encontrado, Punto no existe).
  - operativo=No (crea stage 3 + adjunto). Incluye la regresión real de OBS-10 en I.
  - Vincular a solicitud existente (no crear duplicado).
  - Proximidad temporal + archivado (MP).
  - Verificación de campos del request creado (tipo, stage, técnico, fecha de cierre).
  - R calibración con destino Bodega → equipo a 594.

Usa equipos QA dedicados y resetea su estado de solicitudes para ser repetible.
NO limpia los registros creados (decisión del usuario).
"""

import time

import pandas as pd
import pytest

import processor

pytestmark = pytest.mark.integration

PUNTO_ID = 7
PUNTO_FORM = "Presurizadoras 2 [SSR Los Almendros]"   # [proyecto] -> '[SSR Los Almendros] Presurizadoras 2'
OTRO_PUNTO_ID = 8
FECHA = time.strftime("%Y-%m-%d %H:%M:%S")


def _row(ot, tipo, punto=PUNTO_FORM):
    return {"#": ot, "user": 0, "Fecha visita ": FECHA, "Nombre del Cliente": "QA E2E",
            "1.1 Punto de monitoreo": punto, "1.2 Tipo de trabajo a realizar": tipo,
            "1.3 Resolución de visita": "QA", "1.4 Fotos recinto": ["sim://qa"]}


def _mc(ot, serial, operativo, punto=PUNTO_FORM):
    r = _row(ot, "MC", punto)
    r.update({"1.2.1 MC | Modelo": "QA", "1.2.1 MC | Activo a intervenir": "Caudalímetro",
              "1.2.1 MC | N° de serie": serial,
              "1.2.1 MC | ¿Equipo operativo tras trabajos?": operativo,
              "1.2.1 MC | Observación": "QA"})
    return pd.DataFrame([r])


def _cf(ot, serial, operativo):
    r = _row(ot, "CF")
    r.update({"1.2.1 CF | Modelo": "QA", "1.2.1 CF | Activo a intervenir": "Caudalímetro",
              "1.2.1 CF | N° de serie": serial,
              "1.2.1 CF | ¿Equipo operativo tras trabajos?": operativo,
              "1.2.1 CF | Observación": "QA", "1.2.1 CF | Tipo de Ajuste": "Ajuste QA"})
    return pd.DataFrame([r])


def _mp(ot, serial, operativo):
    r = _row(ot, "MP")
    r.update({"1.2.1 MP (I) | Modelo": "QA",
              "1.2.1 MP (I) | Dispositivo a intervenir": "Caudalímetro",
              "1.2.1 MP (I) | N° de serie": serial,
              "1.2.1 MP (I) | ¿Dispositivo operativo tras trabajos?": operativo,
              "1.2.1 MP (I) | Observación": "QA"})
    return pd.DataFrame([r])


def _i(ot, serial, operativo):
    r = _row(ot, "I")
    r.update({"1.2.1 I (I) | Modelo": "QA", "1.2.1 I (I) | Tipo de dispositivo": "Caudalímetro",
              "1.2.1 I (I) | N° de serie": serial,
              "1.2.1 I (I) | ¿Equipo operativo tras trabajos?": operativo,
              "1.2.1 I (I) | Observación": "QA"})
    return pd.DataFrame([r])


def _r_calibracion(ot, serial_e, serial_i, destino):
    r = _row(ot, "R")
    r.update({"1.2.1 R | Tipo equipo/instrumento a reemplazar": "Caudalímetro",
              "1.2.1 R | Observación": "QA", "1.2.1 R | Motivo de reemplazo": "Ciclo de calibración",
              "1.2.1 R (E) | Modelo": "QA-E", "1.2.1 R (E) | N° de serie": serial_e,
              "1.2.1 R (E) | Destino": destino,
              "1.2.1 R (I) | Modelo": "QA-I", "1.2.1 R (I) | N° de serie": serial_i})
    return pd.DataFrame([r])


def _inbox_msgs(odoo, ot):
    recs = odoo.search_read("x_inbox_integracion", [["x_name", "=", f"OT: {ot}"]],
                            fields=["x_studio_mensaje"])
    return " | ".join((r.get("x_studio_mensaje") or "") for r in recs)


def _loc(odoo, eid):
    v = odoo.read("maintenance.equipment", [eid], fields=["x_studio_location"])[0]["x_studio_location"]
    return v[0] if v else False


def _corrective(odoo, eid):
    return set(odoo.search("maintenance.request",
                           [["equipment_id", "=", eid],
                            ["x_studio_tipo_de_trabajo", "=", "Mantención Correctiva"]]))


# ----------------------------- Excepciones (read-back del inbox) -----------------------------
def test_e2e_exc_sn_no_encontrado(odoo, e2e_ctx):
    ot = 990201
    resumen, exito = e2e_ctx
    processor.process_entrys(_mc(ot, "QA-SN-INEXISTENTE-990201", "Sí"), "K", resumen, exito, odoo)
    msgs = _inbox_msgs(odoo, ot)
    assert "no encontrado" in msgs.lower(), f"inbox OT {ot}: {msgs!r}"


def test_e2e_exc_punto_no_existe(odoo, ensure_equipment, e2e_ctx):
    ot = 990202
    eid = ensure_equipment("QA-EXC-PT", "QA Excepción punto", location_id=PUNTO_ID)
    resumen, exito = e2e_ctx
    processor.process_entrys(
        _mc(ot, "QA-EXC-PT", "Sí", punto="Punto Fantasma QA [Proyecto Fantasma]"),
        "K", resumen, exito, odoo)
    msgs = _inbox_msgs(odoo, ot)
    assert "no se encuentra listado" in msgs.lower(), f"inbox OT {ot}: {msgs!r}"


# ----------------------------- operativo = No (crea stage 3 + adjunto) -----------------------------
def test_e2e_mc_no_operativo_crea_stage3(odoo, ensure_equipment, reset_requests, e2e_ctx):
    eid = ensure_equipment("QA-MC-NO", "QA MC no operativo", location_id=PUNTO_ID)
    reset_requests(eid)
    antes = _corrective(odoo, eid)
    resumen, exito = e2e_ctx
    processor.process_entrys(_mc(990203, "QA-MC-NO", "No"), "K", resumen, exito, odoo)
    nuevas = _corrective(odoo, eid) - antes
    assert nuevas, "debía crear una solicitud correctiva"
    rec = odoo.read("maintenance.request", [list(nuevas)[0]], fields=["stage_id"])[0]
    assert rec["stage_id"][0] == 3, f"stage esperado 3 (En proceso); fue {rec['stage_id']}"


def test_e2e_i_no_operativo_regresion_obs10(odoo, ensure_equipment, reset_requests, e2e_ctx):
    """Regresión REAL de OBS-10: antes este path lanzaba NameError y no registraba
    éxito. Tras la corrección, debe registrar el éxito de la instalación.
    Se resetean las solicitudes para forzar el path de CREACIÓN (el del bug)."""
    eid = ensure_equipment("QA-I-NO", "QA I no operativo", location_id=PUNTO_ID)
    reset_requests(eid)
    resumen, exito = e2e_ctx
    processor.process_entrys(_i(990204, "QA-I-NO", "No"), "K", resumen, exito, odoo)
    assert any("instalación" in m.lower() for m in exito["Mensaje"]), \
        f"OBS-10: debía registrar éxito de instalación; exito={exito['Mensaje']}"


def test_e2e_cf_no_operativo_crea_stage3(odoo, ensure_equipment, reset_requests, e2e_ctx):
    eid = ensure_equipment("QA-CF-NO", "QA CF no operativo", location_id=PUNTO_ID)
    reset_requests(eid)
    antes = set(odoo.search("maintenance.request",
                            [["equipment_id", "=", eid], ["x_studio_tipo_de_trabajo", "=", "Configuración"]]))
    resumen, exito = e2e_ctx
    processor.process_entrys(_cf(990205, "QA-CF-NO", "No"), "K", resumen, exito, odoo)
    nuevas = set(odoo.search("maintenance.request",
                             [["equipment_id", "=", eid], ["x_studio_tipo_de_trabajo", "=", "Configuración"]])) - antes
    assert nuevas, "debía crear una configuración"
    assert odoo.read("maintenance.request", [list(nuevas)[0]], fields=["stage_id"])[0]["stage_id"][0] == 3


# ----------------------------- Vincular a solicitud existente -----------------------------
def test_e2e_mc_vincula_existente(odoo, ensure_equipment, reset_requests, seed_request, e2e_ctx):
    eid = ensure_equipment("QA-MC-UPD", "QA MC vincular", location_id=PUNTO_ID)
    reset_requests(eid)
    seed = seed_request(eid, "Mantención Correctiva", "corrective", "2026-05-20 10:00:00")
    antes = _corrective(odoo, eid)
    resumen, exito = e2e_ctx
    processor.process_entrys(_mc(990206, "QA-MC-UPD", "Sí"), "K", resumen, exito, odoo)
    despues = _corrective(odoo, eid)
    assert despues == antes, f"no debía crear nueva solicitud; nuevas={despues - antes}"
    assert odoo.read("maintenance.request", [seed], fields=["stage_id"])[0]["stage_id"][0] == 5, \
        "la solicitud existente debía quedar Finalizada (stage 5)"


def test_e2e_mp_proximidad_archiva_la_anterior(odoo, ensure_equipment, reset_requests, seed_request, e2e_ctx):
    eid = ensure_equipment("QA-MP-PROX", "QA MP proximidad", location_id=PUNTO_ID)
    reset_requests(eid)
    vieja = seed_request(eid, "Mantención Preventiva", "preventive", "2026-04-01 10:00:00")
    cercana = seed_request(eid, "Mantención Preventiva", "preventive", "2026-05-20 10:00:00")
    resumen, exito = e2e_ctx
    processor.process_entrys(_mp(990207, "QA-MP-PROX", "Sí"), "K", resumen, exito, odoo)
    assert odoo.read("maintenance.request", [cercana], fields=["stage_id"])[0]["stage_id"][0] == 5, \
        "la solicitud más cercana debía finalizarse (stage 5)"
    # El módulo archiva con un campo custom 'archive' (no el 'active' estándar de Odoo).
    assert odoo.read("maintenance.request", [vieja], fields=["archive"])[0]["archive"] is True, \
        "la solicitud anterior debía quedar archivada (archive=True)"


# ----------------------------- Verificación de campos del request creado -----------------------------
def test_e2e_mc_campos_del_request(odoo, ensure_equipment, reset_requests, e2e_ctx):
    eid = ensure_equipment("QA-MC-FIELDS", "QA MC campos", location_id=PUNTO_ID)
    reset_requests(eid)
    antes = _corrective(odoo, eid)
    resumen, exito = e2e_ctx
    processor.process_entrys(_mc(990208, "QA-MC-FIELDS", "Sí"), "K", resumen, exito, odoo)
    nuevas = _corrective(odoo, eid) - antes
    assert nuevas, "debía crear la solicitud"
    rec = odoo.read("maintenance.request", [list(nuevas)[0]],
                    fields=["x_studio_tipo_de_trabajo", "stage_id", "x_studio_tcnico", "close_date"])[0]
    assert rec["x_studio_tipo_de_trabajo"] == "Mantención Correctiva"
    assert rec["stage_id"][0] == 5
    assert rec["x_studio_tcnico"] and rec["x_studio_tcnico"][0] == 145, "técnico Diego Marchant (145)"
    assert rec["close_date"], "debía fijar fecha de cierre"


# ----------------------------- R calibración con destino Bodega -----------------------------
def test_e2e_r_calibracion_bodega_mueve_a_594(odoo, ensure_equipment, e2e_ctx):
    eid_e = ensure_equipment("QA-RB-E", "QA R Bodega saliente", location_id=PUNTO_ID)
    eid_i = ensure_equipment("QA-RB-I", "QA R Bodega entrante", location_id=OTRO_PUNTO_ID)
    resumen, exito = e2e_ctx
    processor.process_entrys(_r_calibracion(990209, "QA-RB-E", "QA-RB-I", "Bodega cliente"),
                             "K", resumen, exito, odoo)
    assert _loc(odoo, eid_e) == 594, f"saliente debía ir a Bodega (594); está en {_loc(odoo, eid_e)}"
