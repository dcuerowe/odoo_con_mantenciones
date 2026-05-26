"""Fixtures compartidas por la capa de integración (L3).

`odoo`: cliente OdooClient autenticado contra el test-Odoo. Se omite (skip) salvo
RUN_ODOO_INTEGRATION=1, y aborta si config no apunta a URL_TEST (no tocar producción).
"""

import os

import pytest


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
