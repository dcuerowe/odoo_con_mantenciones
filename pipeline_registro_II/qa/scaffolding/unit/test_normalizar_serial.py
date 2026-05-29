"""L1 · Unitario — processor.normalizar_serial (corrección OBS-11).

El serial se busca en Odoo con coincidencia EXACTA contra el campo char serial_no.
pandas puede inferir un serial numérico como float (24000.0); normalizar_serial debe
entregar un string limpio que calce ("24000"), sin romper los serials alfanuméricos.
"""

import pytest

import processor


@pytest.mark.parametrize("entrada, esperado", [
    (24000.0, "24000"),            # float entero -> sin ".0"
    (24000, "24000"),              # int -> string
    ("24000", "24000"),            # ya string, sin cambios
    ("24000WE0000221", "24000WE0000221"),  # alfanumérico se preserva
    ("  SN-123  ", "SN-123"),      # recorta espacios
    (24000.5, "24000.5"),          # float no entero conserva decimales
])
def test_normalizar_serial(entrada, esperado):
    assert processor.normalizar_serial(entrada) == esperado


def test_normalizar_serial_resultado_es_string():
    assert isinstance(processor.normalizar_serial(24000.0), str)


def test_normalizar_serial_none_se_preserva():
    assert processor.normalizar_serial(None) is None
