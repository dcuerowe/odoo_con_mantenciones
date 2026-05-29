"""Configuración compartida de pytest para la suite de QA.

- Inserta `pipeline_registro_II/` en sys.path para importar processor, data_processing, etc.
- Inserta el dir del scaffolding para importar `odoo_spy`.
- Expone fixtures comunes: `spy`, `acc` (acumuladores resumen/exito), `mc_dataframe`.
"""

import io
import sys
from pathlib import Path

import pytest

SCAFFOLD_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = SCAFFOLD_DIR.parents[1]  # qa/scaffolding -> qa -> pipeline_registro_II

for p in (str(PIPELINE_DIR), str(SCAFFOLD_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


# Columnas de los acumuladores, idénticas a las que arma main.job().
ACC_COLS = ("OT", "Técnico", "Fecha de revisión", "Proyecto", "Punto de monitoreo",
            "Equipo/instrumento", "Modelo", "N° serie", "Tipo", "Mensaje")


@pytest.fixture
def spy():
    from odoo_spy import OdooSpy
    return OdooSpy()


@pytest.fixture
def acc():
    """Devuelve (resumen, exito) recién inicializados, como en main.job()."""
    def fresh():
        return {k: [] for k in ACC_COLS}
    return fresh(), fresh()


@pytest.fixture
def patch_externals(monkeypatch):
    """Parchea los bordes externos que `processor` importó por nombre:
    `processor.user` (HTTP Connecteam) y `processor.informe_pdf_profesional`
    (HTTP imágenes + reportlab). Devuelve el nombre de técnico usado, que existe
    en el dict `operators` de processor (→ id 145)."""
    import processor

    tecnico = "Diego Marchant"
    monkeypatch.setattr(processor, "user", lambda *a, **k: tecnico)
    # process_entrys hace pdf.seek(0)/pdf.read() → devolver un stream, no un str.
    monkeypatch.setattr(processor, "informe_pdf_profesional",
                        lambda *a, **k: io.BytesIO(b"%PDF-1.4 dummy QA"))
    return tecnico
