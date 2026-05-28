"""Fixtures compartidas por la capa de integración (L3).

`odoo`: cliente OdooClient autenticado contra el test-Odoo. Se omite (skip) salvo
RUN_ODOO_INTEGRATION=1, y aborta si config no apunta a URL_TEST (no tocar producción).
"""

import json
import os
from pathlib import Path

import pytest

# Colector de objetos creados en el test-Odoo durante la corrida (para el reporte).
_CREATED = []
_OBJ_PATH = Path(os.environ.get("QA_OBJ_PATH", "/tmp/qa_run/objetos.json"))


@pytest.fixture(autouse=True)
def _capture_creates(request, odoo):
    """Envuelve odoo.create durante cada prueba de integración y registra cada
    objeto creado (modelo, id, etiqueta) asociándolo a la prueba. Así el reporte
    documenta la vinculación con los registros reales del test-Odoo."""
    orig = odoo.create

    def wrapped(model, values):
        rid = orig(model, values)
        _CREATED.append({
            "test": request.node.name,
            "model": model,
            "id": rid,
            "label": (values.get("name") or values.get("x_name") or "")[:60],
        })
        return rid

    odoo.create = wrapped
    try:
        yield
    finally:
        odoo.create = orig


def pytest_sessionfinish(session, exitstatus):
    try:
        _OBJ_PATH.parent.mkdir(parents=True, exist_ok=True)
        _OBJ_PATH.write_text(json.dumps(_CREATED, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


@pytest.fixture(scope="module")
def odoo():
    if os.getenv("RUN_ODOO_INTEGRATION") != "1":
        pytest.skip("RUN_ODOO_INTEGRATION!=1 — se omiten las pruebas de integración")

    import config
    from odoo_client import OdooClient

    url_test = os.getenv("URL_TEST")
    if not url_test:
        pytest.skip("URL_TEST no está en el entorno (.env ausente): no hay test-Odoo que probar")
    assert config.ODOO_URL == url_test, (
        "config.py NO apunta a URL_TEST. Aborta para no escribir en producción. "
        f"(ODOO_URL={config.ODOO_URL!r}, URL_TEST={url_test!r})")

    client = OdooClient(config.ODOO_URL, config.ODOO_DB, config.ODOO_USER, config.ODOO_PASSWORD)
    uid = client.authenticate()
    assert uid, "Autenticación con test-Odoo falló (uid vacío)"
    return client


ACC_COLS = ("OT", "Técnico", "Fecha de revisión", "Proyecto", "Punto de monitoreo",
            "Equipo/instrumento", "Modelo", "N° serie", "Tipo", "Mensaje")


@pytest.fixture
def e2e_ctx(monkeypatch):
    """Parchea los bordes NO-Odoo (técnico Connecteam + PDF) y entrega
    los acumuladores (resumen, exito) que usa process_entrys."""
    import io
    import processor
    monkeypatch.setattr(processor, "user", lambda *a, **k: "Diego Marchant")
    monkeypatch.setattr(processor, "informe_pdf_profesional",
                        lambda *a, **k: io.BytesIO(b"%PDF-1.4 QA E2E"))
    return {k: [] for k in ACC_COLS}, {k: [] for k in ACC_COLS}


@pytest.fixture
def reset_requests(odoo):
    """Finaliza (stage 5) todas las solicitudes activas de un equipo para partir de
    un estado conocido → hace repetibles los tests de 'crear' y 'vincular'.
    Devuelve la función."""
    def _reset(equipment_id):
        ids = odoo.search("maintenance.request", [["equipment_id", "=", equipment_id]])
        if ids:
            odoo.write("maintenance.request", ids, {"stage_id": 5})
        return ids
    return _reset


@pytest.fixture
def seed_request(odoo):
    """Crea una solicitud de prueba para un equipo (estado por defecto = activa).
    Devuelve el id creado."""
    def _seed(equipment_id, tipo_trabajo, mtype, schedule):
        return odoo.create("maintenance.request", {
            "name": f"QA seed {tipo_trabajo}",
            "equipment_id": equipment_id,
            "maintenance_type": mtype,
            "x_studio_tipo_de_trabajo": tipo_trabajo,
            "schedule_date": schedule,
        })
    return _seed


@pytest.fixture
def ensure_equipment(odoo):
    """Crea (si no existe) un maintenance.equipment de QA por serial y FIJA su
    ubicación-precondición. Reutiliza por serial → re-ejecutar no duplica equipos,
    y resetear la ubicación hace repetibles los tests de movimiento (I y R).
    Devuelve el id del equipo."""
    def _ensure(serial, name, location_id=False):
        ids = odoo.search("maintenance.equipment", [["serial_no", "=", serial]], limit=1)
        eid = ids[0] if ids else odoo.create(
            "maintenance.equipment", {"name": name, "serial_no": serial})
        odoo.write("maintenance.equipment", [eid], {"x_studio_location": location_id})
        return eid
    return _ensure
