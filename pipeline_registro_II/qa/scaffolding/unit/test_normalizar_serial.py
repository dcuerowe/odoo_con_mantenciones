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
    # En Odoo no existen S/N numéricos con ceros a la izquierda: se eliminan.
    ("04245245", "4245245"),       # cero líder en numérico puro -> se quita
    ("0024000", "24000"),          # varios ceros líderes -> se quitan todos
    ("  007  ", "7"),              # recorta espacios y luego quita ceros
    ("000", "0"),                  # todo ceros -> no queda vacío, se preserva "0"
    ("WE0000221", "WE0000221"),    # alfanumérico con ceros NO se toca
    ("0WE221", "0WE221"),          # cero líder pero alfanumérico -> se preserva
])
def test_normalizar_serial(entrada, esperado):
    assert processor.normalizar_serial(entrada) == esperado


def test_normalizar_serial_resultado_es_string():
    assert isinstance(processor.normalizar_serial(24000.0), str)


def test_normalizar_serial_none_se_preserva():
    assert processor.normalizar_serial(None) is None
