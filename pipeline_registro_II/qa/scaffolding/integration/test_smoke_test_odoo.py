"""L3 · Smoke E2E contra test-Odoo real. ESCRIBE/lee en la instancia de test.

Se omite salvo RUN_ODOO_INTEGRATION=1. Salvaguarda dura: aborta si config no
apunta a URL_TEST (REQ-ISO-1).
"""

import pytest

pytestmark = pytest.mark.integration

# El fixture `odoo` está en integration/conftest.py (compartido con el E2E de escritura).


def test_autenticacion(odoo):
    assert odoo.uid


def test_lectura_modelo_base(odoo):
    res = odoo.search_read("maintenance.equipment", [], fields=["id"], limit=1)
    assert isinstance(res, list)


def test_partners_load_bearing_existen(odoo):
    """R3: los res.partner hardcodeados deben existir en el test-Odoo.
    Followers del inbox (5205 Felipe, 172 Rodrigo, 158 Juan), técnico Metrocal (5118)
    y un operador de muestra (145 Diego). Si alguno falta, los followers/asignaciones
    fallan silenciosamente en producción del pipeline."""
    requeridos = {5205, 172, 158, 5118, 145}
    encontrados = set(odoo.search("res.partner", [["id", "in", list(requeridos)]]))
    faltantes = requeridos - encontrados
    assert not faltantes, f"res.partner inexistentes en test-Odoo: {faltantes}"


def test_team_y_ubicaciones_metrocal_existen(odoo):
    """R3: maintenance.team 2 (Metrocal) y las ubicaciones de calibración
    x_maintenance_location 593 (Laboratorio) / 594 (Bodega cliente) usadas por el módulo R."""
    assert odoo.search("maintenance.team", [["id", "=", 2]]), "maintenance.team 2 no existe"
    locs = set(odoo.search("x_maintenance_location", [["id", "in", [593, 594]]]))
    assert {593, 594} <= locs, f"ubicaciones 593/594 faltan en test-Odoo: {{593,594}} - {locs}"
