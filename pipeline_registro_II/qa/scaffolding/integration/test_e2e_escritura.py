"""L3 · E2E de ESCRITURA contra el test-Odoo (staging).

ESCRIBE registros reales: ejecuta process_entrys de punta a punta para una OT de QA
reservada y verifica que el pipeline creó el inbox y la solicitud en el staging.
NO limpia: los registros quedan para inspección manual (decisión del usuario, 2026-05-26).

Datos reales del staging (descubiertos read-only):
  equipo id 10 · serial 24000WE0000221 · ubicación '[Los Bronces - Riecillos] R3050 Caudalimetro D'.

Bordes externos NO-Odoo parcheados (Connecteam y generación de PDF) para que el test
sea determinista; las escrituras a Odoo SÍ son reales.

Re-ejecutar crea registros duplicados (la OT no se deduplica aquí porque se llama a
process_entrys directo, sin check_new_sub).
"""

import io
import time

import pandas as pd
import pytest

import processor

pytestmark = pytest.mark.integration

OT_QA = 990001
SERIAL = "24000WE0000221"
# Formato del formulario: "Punto [Proyecto]" (process_entrys extrae el proyecto del corchete).
PUNTO_FORM = "R3050 Caudalimetro D [Los Bronces - Riecillos]"

ACC_COLS = ("OT", "Técnico", "Fecha de revisión", "Proyecto", "Punto de monitoreo",
            "Equipo/instrumento", "Modelo", "N° serie", "Tipo", "Mensaje")


def _mc_dataframe():
    row = {
        "#": OT_QA, "user": 0,
        "Fecha visita ": time.strftime("%Y-%m-%d %H:%M:%S"),
        "Nombre del Cliente": "QA E2E",
        "1.1 Punto de monitoreo": PUNTO_FORM,
        "1.2 Tipo de trabajo a realizar": "MC",
        "1.3 Resolución de visita": "Registro E2E de QA",
        "1.4 Fotos recinto": ["sim://qa"],
        "1.2.1 MC | Modelo": "QA-E2E",
        "1.2.1 MC | Activo a intervenir": "Caudalímetro",
        "1.2.1 MC | N° de serie": SERIAL,
        "1.2.1 MC | ¿Equipo operativo tras trabajos?": "Sí",
        "1.2.1 MC | Observación": "Registro E2E de QA (creado por la suite de pruebas)",
    }
    return pd.DataFrame([row])


def test_e2e_mc_escribe_solicitud_e_inbox(odoo, monkeypatch):
    # Bordes NO-Odoo: técnico (Connecteam) y PDF (reportlab/HTTP).
    monkeypatch.setattr(processor, "user", lambda *a, **k: "Diego Marchant")
    monkeypatch.setattr(processor, "informe_pdf_profesional",
                        lambda *a, **k: io.BytesIO(b"%PDF-1.4 QA E2E"))

    resumen = {k: [] for k in ACC_COLS}
    exito = {k: [] for k in ACC_COLS}

    # Estado previo: cuántas solicitudes MC tiene el equipo antes de correr.
    eq_ids = odoo.search("maintenance.equipment", [["serial_no", "=", SERIAL]], limit=1)
    assert eq_ids, f"el equipo de prueba (serial {SERIAL}) ya no existe en el staging"
    dominio_mc = [["equipment_id", "=", eq_ids[0]],
                  ["x_studio_tipo_de_trabajo", "=", "Mantención Correctiva"]]
    reqs_antes = set(odoo.search("maintenance.request", dominio_mc))

    # --- ESCRITURA REAL ---
    processor.process_entrys(_mc_dataframe(), "KEY", resumen, exito, odoo)

    # 1) Se creó el registro de inbox de la OT (prueba limpia: OT 990001 no tenía inbox previo).
    inbox = odoo.search_read("x_inbox_integracion", [["x_name", "=", f"OT: {OT_QA}"]],
                             fields=["id", "x_studio_mensaje"])
    assert inbox, "el pipeline no creó el registro de inbox de la OT en el staging"

    # 2) Apareció al menos una solicitud MC nueva para el equipo.
    reqs_despues = set(odoo.search("maintenance.request", dominio_mc))
    nuevas = reqs_despues - reqs_antes
    assert nuevas, ("no se creó una nueva maintenance.request MC para el equipo "
                    f"(antes={len(reqs_antes)}, después={len(reqs_despues)})")

    print(f"\nE2E OK · inbox={[i['id'] for i in inbox]} · "
          f"requests_MC_nuevas={sorted(nuevas)} · exito.Mensaje={exito['Mensaje']}")
