"""L3 · E2E de ESCRITURA por flujo, contra el test-Odoo (staging).

Un test por tipo de trabajo. Énfasis en I y R, que MUEVEN la ubicación del equipo
(x_studio_location) — esos tests resetean la ubicación-precondición y verifican el
movimiento resultante en el equipo real (QA).

Equipos QA dedicados (no se tocan equipos reales). NO se limpian los registros
creados (solicitudes/inbox); los equipos QA se reutilizan por serial.

Punto de servicio usado: id 7 = '[SSR Los Almendros] Presurizadoras 2'.
Ubicaciones de calibración (módulo R): 593 = Laboratorio | Metrocal, 594 = Bodega cliente.
"""

import time

import pandas as pd
import pytest

import processor

pytestmark = pytest.mark.integration

# Punto de servicio (existe en staging). Formato de formulario: "Punto [Proyecto]".
PUNTO_ID = 7
PROYECTO = "SSR Los Almendros"
PUNTO = "Presurizadoras 2"
PUNTO_FORM = f"{PUNTO} [{PROYECTO}]"
OTRO_PUNTO_ID = 8  # para forzar "cambio de ubicación" en I
LAB_LOC = 593

ACC_COLS = ("OT", "Técnico", "Fecha de revisión", "Proyecto", "Punto de monitoreo",
            "Equipo/instrumento", "Modelo", "N° serie", "Tipo", "Mensaje")


@pytest.fixture
def run_ctx(monkeypatch):
    """Parchea los bordes NO-Odoo (técnico Connecteam + PDF) y entrega acumuladores."""
    monkeypatch.setattr(processor, "user", lambda *a, **k: "Diego Marchant")
    monkeypatch.setattr(processor, "informe_pdf_profesional",
                        lambda *a, **k: __import__("io").BytesIO(b"%PDF-1.4 QA E2E"))
    return {k: [] for k in ACC_COLS}, {k: [] for k in ACC_COLS}


def _base_row(ot, tipo_trabajo):
    return {
        "#": ot, "user": 0,
        "Fecha visita ": time.strftime("%Y-%m-%d %H:%M:%S"),
        "Nombre del Cliente": "QA E2E",
        "1.1 Punto de monitoreo": PUNTO_FORM,
        "1.2 Tipo de trabajo a realizar": tipo_trabajo,
        "1.3 Resolución de visita": "Registro E2E de QA",
        "1.4 Fotos recinto": ["sim://qa"],
    }


def _equipo_de(odoo, serial):
    return odoo.search("maintenance.equipment", [["serial_no", "=", serial]], limit=1)[0]


def _requests(odoo, equipment_id, tipo_trabajo):
    return set(odoo.search("maintenance.request",
                           [["equipment_id", "=", equipment_id],
                            ["x_studio_tipo_de_trabajo", "=", tipo_trabajo]]))


def _location_id(odoo, equipment_id):
    loc = odoo.read("maintenance.equipment", [equipment_id],
                    fields=["x_studio_location"])[0]["x_studio_location"]
    return loc[0] if loc else False


# --------------------------------------------------------------------------- #
# CF — Configuración (sin movimiento de equipo)
# --------------------------------------------------------------------------- #
def test_e2e_cf_crea_configuracion(odoo, ensure_equipment, run_ctx):
    resumen, exito = run_ctx
    eid = ensure_equipment("QA-E2E-CF", "QA E2E Configuración", location_id=PUNTO_ID)
    antes = _requests(odoo, eid, "Configuración")

    row = _base_row(990010, "CF")
    row.update({
        "1.2.1 CF | Modelo": "QA-E2E",
        "1.2.1 CF | Activo a intervenir": "Caudalímetro",
        "1.2.1 CF | N° de serie": "QA-E2E-CF",
        "1.2.1 CF | ¿Equipo operativo tras trabajos?": "Sí",
        "1.2.1 CF | Observación": "E2E QA",
        "1.2.1 CF | Tipo de Ajuste": "Ajuste de fábrica",
    })
    processor.process_entrys(pd.DataFrame([row]), "KEY", resumen, exito, odoo)

    nuevas = _requests(odoo, eid, "Configuración") - antes
    assert nuevas, f"no se creó solicitud CF (exito={exito['Mensaje']})"
    print(f"\nCF OK · requests nuevas={sorted(nuevas)}")


# --------------------------------------------------------------------------- #
# MP — Mantención Preventiva (sin movimiento de equipo)
# --------------------------------------------------------------------------- #
def test_e2e_mp_crea_preventiva(odoo, ensure_equipment, run_ctx):
    resumen, exito = run_ctx
    eid = ensure_equipment("QA-E2E-MP", "QA E2E Preventiva", location_id=PUNTO_ID)
    antes = _requests(odoo, eid, "Mantención Preventiva")

    row = _base_row(990011, "MP")
    row.update({
        "1.2.1 MP (I) | Modelo": "QA-E2E",
        "1.2.1 MP (I) | Dispositivo a intervenir": "Caudalímetro",
        "1.2.1 MP (I) | N° de serie": "QA-E2E-MP",
        "1.2.1 MP (I) | ¿Dispositivo operativo tras trabajos?": "Sí",
        "1.2.1 MP (I) | Observación": "E2E QA",
    })
    processor.process_entrys(pd.DataFrame([row]), "KEY", resumen, exito, odoo)

    nuevas = _requests(odoo, eid, "Mantención Preventiva") - antes
    assert nuevas, f"no se creó solicitud MP (exito={exito['Mensaje']})"
    print(f"\nMP OK · requests nuevas={sorted(nuevas)}")


# --------------------------------------------------------------------------- #
# I — Instalación (MUEVE ubicación del equipo)
# --------------------------------------------------------------------------- #
def test_e2e_i_sin_ubicacion_asocia_al_punto(odoo, ensure_equipment, run_ctx):
    """Equipo sin ubicación (False) → I debe escribir x_studio_location = punto."""
    resumen, exito = run_ctx
    eid = ensure_equipment("QA-E2E-I", "QA E2E Instalación", location_id=False)
    assert _location_id(odoo, eid) is False, "precondición: el equipo debía quedar sin ubicación"

    row = _base_row(990012, "I")
    row.update({
        "1.2.1 I (I) | Modelo": "QA-E2E",
        "1.2.1 I (I) | Tipo de dispositivo": "Caudalímetro",
        "1.2.1 I (I) | N° de serie": "QA-E2E-I",
        "1.2.1 I (I) | ¿Equipo operativo tras trabajos?": "Sí",
        "1.2.1 I (I) | Observación": "E2E QA",
    })
    processor.process_entrys(pd.DataFrame([row]), "KEY", resumen, exito, odoo)

    assert _location_id(odoo, eid) == PUNTO_ID, (
        f"el equipo no quedó asociado al punto {PUNTO_ID} (location actual="
        f"{_location_id(odoo, eid)})")
    print(f"\nI(sin ubicación) OK · equipo {eid} → punto {PUNTO_ID}")


def test_e2e_i_cambio_de_ubicacion(odoo, ensure_equipment, run_ctx):
    """Equipo en OTRO punto → I debe moverlo al punto del formulario."""
    resumen, exito = run_ctx
    eid = ensure_equipment("QA-E2E-I", "QA E2E Instalación", location_id=OTRO_PUNTO_ID)
    assert _location_id(odoo, eid) == OTRO_PUNTO_ID

    row = _base_row(990013, "I")
    row.update({
        "1.2.1 I (I) | Modelo": "QA-E2E",
        "1.2.1 I (I) | Tipo de dispositivo": "Caudalímetro",
        "1.2.1 I (I) | N° de serie": "QA-E2E-I",
        "1.2.1 I (I) | ¿Equipo operativo tras trabajos?": "Sí",
        "1.2.1 I (I) | Observación": "E2E QA",
    })
    processor.process_entrys(pd.DataFrame([row]), "KEY", resumen, exito, odoo)

    assert _location_id(odoo, eid) == PUNTO_ID, (
        f"el equipo no se movió de {OTRO_PUNTO_ID} a {PUNTO_ID} "
        f"(actual={_location_id(odoo, eid)})")
    print(f"\nI(cambio ubicación) OK · equipo {eid} {OTRO_PUNTO_ID} → {PUNTO_ID}")


# --------------------------------------------------------------------------- #
# R — Reemplazo/Extracción · Ciclo de calibración (MUEVE ambos equipos)
# --------------------------------------------------------------------------- #
def test_e2e_r_calibracion_mueve_equipos(odoo, ensure_equipment, run_ctx):
    """Calibración: el saliente (E, destino Laboratorio) → 593; el entrante (I) → punto.
    Verifica el movimiento real de ambos equipos QA."""
    resumen, exito = run_ctx
    eid_e = ensure_equipment("QA-E2E-R-E", "QA E2E Reemplazo saliente", location_id=PUNTO_ID)
    eid_i = ensure_equipment("QA-E2E-R-I", "QA E2E Reemplazo entrante", location_id=OTRO_PUNTO_ID)

    row = _base_row(990014, "R")
    row.update({
        "1.2.1 R | Tipo equipo/instrumento a reemplazar": "Caudalímetro",
        "1.2.1 R | Observación": "E2E QA",
        "1.2.1 R | Motivo de reemplazo": "Ciclo de calibración",
        "1.2.1 R (E) | Modelo": "QA-E2E-E",
        "1.2.1 R (E) | N° de serie": "QA-E2E-R-E",
        "1.2.1 R (E) | Destino": "Laboratorio | Metrocal",
        "1.2.1 R (I) | Modelo": "QA-E2E-I",
        "1.2.1 R (I) | N° de serie": "QA-E2E-R-I",
    })
    processor.process_entrys(pd.DataFrame([row]), "KEY", resumen, exito, odoo)

    loc_e = _location_id(odoo, eid_e)
    loc_i = _location_id(odoo, eid_i)
    assert loc_e == LAB_LOC, f"el saliente no fue al Laboratorio (593); location={loc_e}"
    assert loc_i == PUNTO_ID, f"el entrante no fue al punto {PUNTO_ID}; location={loc_i}"
    print(f"\nR(calibración) OK · saliente {eid_e}→593 · entrante {eid_i}→{PUNTO_ID}")
