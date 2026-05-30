"""L1 · Unitario — processor._buscar_equipo_por_serial.

Cubre el árbol de decisión completo del nuevo modo de búsqueda numérica:

  * serial NO puramente numérico         → búsqueda exacta de siempre
  * serial puramente numérico            → substring sobre universo restringido
                                            (.isdigit() o contiene "WE")
    - 0 matches                          → no encontrado
    - 1 match                            → ese
    - exacta única (regla universal)     → la exacta
    - >1 exactas                         → no encontrado
    - solo numéricas sin exacta          → no encontrado
    - solo WE                            → no encontrado
    - mixto, len > 4, sin exacta         → no encontrado
    - mixto, len ≤ 4, 1 WE               → la WE
    - mixto, len ≤ 4, >1 WE              → no encontrado
"""

import processor


# ---------- serial alfanumérico: ruta exacta ---------- #
def test_alfanumerico_usa_busqueda_exacta(spy):
    spy.set_default("search_read", "maintenance.equipment",
                    [{"id": 1, "serial_no": "SN-XYZ"}])
    res = processor._buscar_equipo_por_serial(spy, "SN-XYZ")
    assert len(res) == 1 and res[0]["id"] == 1
    dominio = spy.calls_of("search_read", "maintenance.equipment")[0].args[0]
    assert dominio == [["serial_no", "=", "SN-XYZ"]]


def test_alfanumerico_sin_match_devuelve_lista_vacia(spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    assert processor._buscar_equipo_por_serial(spy, "SN-404") == []


def test_serial_vacio_o_none_no_consulta_odoo(spy):
    assert processor._buscar_equipo_por_serial(spy, "") == []
    assert processor._buscar_equipo_por_serial(spy, None) == []
    assert spy.calls_of("search_read", "maintenance.equipment") == []


# ---------- numérico puro: dominio del search ---------- #
def test_numerico_dispara_busqueda_por_substring(spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    processor._buscar_equipo_por_serial(spy, "24000")
    dominio = spy.calls_of("search_read", "maintenance.equipment")[0].args[0]
    valores = [c[2] for c in dominio if isinstance(c, (list, tuple)) and len(c) == 3]
    # 24000 debe ir como pattern 'like', envuelto en %
    assert any(isinstance(v, str) and v == "%24000%" for v in valores), dominio


# ---------- 0 y 1 coincidencias ---------- #
def test_numerico_sin_coincidencias(spy):
    spy.set_default("search_read", "maintenance.equipment", [])
    assert processor._buscar_equipo_por_serial(spy, "24000") == []


def test_numerico_una_coincidencia_we(spy):
    spy.set_default("search_read", "maintenance.equipment",
                    [{"id": 1, "serial_no": "24000WE0000221"}])
    res = processor._buscar_equipo_por_serial(spy, "24000")
    assert len(res) == 1 and res[0]["id"] == 1


def test_numerico_una_coincidencia_numerica(spy):
    spy.set_default("search_read", "maintenance.equipment",
                    [{"id": 1, "serial_no": "24000"}])
    res = processor._buscar_equipo_por_serial(spy, "24000")
    assert len(res) == 1 and res[0]["id"] == 1


# ---------- regla universal: exacta gana ---------- #
def test_multimatch_exacta_gana_a_we(spy):
    spy.set_default("search_read", "maintenance.equipment", [
        {"id": 1, "serial_no": "24000"},           # exacta
        {"id": 2, "serial_no": "24000WE0000221"},  # WE
    ])
    res = processor._buscar_equipo_por_serial(spy, "24000")
    assert len(res) == 1 and res[0]["id"] == 1, "la exacta debe ganar"


def test_multimatch_solo_numericas_con_exacta_gana(spy):
    """Solo numéricas multi-match: si una es exacta, esa es."""
    spy.set_default("search_read", "maintenance.equipment", [
        {"id": 1, "serial_no": "24000"},   # exacta
        {"id": 2, "serial_no": "240005"},
    ])
    res = processor._buscar_equipo_por_serial(spy, "24000")
    assert len(res) == 1 and res[0]["id"] == 1


def test_multimatch_mixto_len_chico_exacta_gana_a_we(spy):
    """Mixto len ≤ 4 con numérica exacta: la exacta gana sobre la WE (regla universal)."""
    spy.set_default("search_read", "maintenance.equipment", [
        {"id": 1, "serial_no": "24"},          # exacta
        {"id": 2, "serial_no": "24WE0000221"},
    ])
    res = processor._buscar_equipo_por_serial(spy, "24")
    assert len(res) == 1 and res[0]["id"] == 1


def test_multimatch_dos_exactas_es_no_encontrado(spy):
    """Duplicado real: dos serials idénticos en Odoo → no encontrado."""
    spy.set_default("search_read", "maintenance.equipment", [
        {"id": 1, "serial_no": "24000"},
        {"id": 2, "serial_no": "24000"},
    ])
    assert processor._buscar_equipo_por_serial(spy, "24000") == []


# ---------- multi-match sin exacta ---------- #
def test_multimatch_solo_numericas_sin_exacta(spy):
    spy.set_default("search_read", "maintenance.equipment", [
        {"id": 1, "serial_no": "240005"},
        {"id": 2, "serial_no": "124000"},
    ])
    assert processor._buscar_equipo_por_serial(spy, "24000") == []


def test_multimatch_solo_we(spy):
    spy.set_default("search_read", "maintenance.equipment", [
        {"id": 1, "serial_no": "24000WE0000221"},
        {"id": 2, "serial_no": "24000WE0000333"},
    ])
    assert processor._buscar_equipo_por_serial(spy, "24000") == []


def test_multimatch_mixto_len_mayor_4_sin_exacta(spy):
    spy.set_default("search_read", "maintenance.equipment", [
        {"id": 1, "serial_no": "240005"},          # numérica, no exacta
        {"id": 2, "serial_no": "24000WE0000221"},  # WE
    ])
    assert processor._buscar_equipo_por_serial(spy, "24000") == []


def test_multimatch_mixto_len_4_una_we(spy):
    """Mixto sin exacta, len ≤ 4, una sola WE → la WE."""
    spy.set_default("search_read", "maintenance.equipment", [
        {"id": 1, "serial_no": "240"},          # numérica substring (no exacta)
        {"id": 2, "serial_no": "24WE0000221"},  # WE única
    ])
    res = processor._buscar_equipo_por_serial(spy, "24")
    assert len(res) == 1 and res[0]["id"] == 2


def test_multimatch_mixto_len_4_varias_we(spy):
    spy.set_default("search_read", "maintenance.equipment", [
        {"id": 1, "serial_no": "240"},
        {"id": 2, "serial_no": "24WE0000221"},
        {"id": 3, "serial_no": "24WE0000333"},
    ])
    assert processor._buscar_equipo_por_serial(spy, "24") == []


# ---------- WE-fallback: normalización de ceros entre WE y cola ---------- #
def test_we_serial_con_ceros_distintos_se_resuelve(spy):
    """Form WE0000000797 (7 ceros) ↔ Odoo WE000000000797 (9 ceros): mismo número
    lógico 797 → calza vía fallback de normalización."""
    spy.queue("search_read", "maintenance.equipment", [])  # exacto: no calza
    spy.queue("search_read", "maintenance.equipment",      # fallback like 'WE%797'
              [{"id": 221, "serial_no": "WE000000000797"}])
    res = processor._buscar_equipo_por_serial(spy, "WE0000000797")
    assert len(res) == 1 and res[0]["id"] == 221


def test_we_serial_prefijo_24000WE_no_calza(spy):
    """Form WE0000000797 NO debe calzar con 24000WE0000797 (estructura distinta:
    el form arranca con WE, el de Odoo tiene 24000 antes)."""
    spy.queue("search_read", "maintenance.equipment", [])  # exacto vacío
    spy.queue("search_read", "maintenance.equipment",      # like 'WE%797'
              [{"id": 220, "serial_no": "24000WE0000797"}])
    assert processor._buscar_equipo_por_serial(spy, "WE0000000797") == []


def test_we_fallback_multiples_we_logicos_es_no_encontrado(spy):
    """Dos serials WE con el mismo número lógico (distinto padding) → ambiguo."""
    spy.queue("search_read", "maintenance.equipment", [])
    spy.queue("search_read", "maintenance.equipment", [
        {"id": 1, "serial_no": "WE000000000797"},   # 9 ceros
        {"id": 2, "serial_no": "WE0797"},            # 1 cero
    ])
    assert processor._buscar_equipo_por_serial(spy, "WE0000000797") == []


def test_we_exacto_no_dispara_fallback(spy):
    """Si la búsqueda exacta calza, el fallback NO se ejecuta."""
    spy.queue("search_read", "maintenance.equipment",
              [{"id": 1, "serial_no": "WE0000000797"}])  # exacto calza
    res = processor._buscar_equipo_por_serial(spy, "WE0000000797")
    assert len(res) == 1 and res[0]["id"] == 1
    # solo 1 search_read disparado (el exacto), no hubo fallback
    assert len(spy.calls_of("search_read", "maintenance.equipment")) == 1


def test_we_con_letras_despues_no_dispara_fallback(spy):
    """Form WE123ABC: post-WE no es solo dígitos → solo camino exacto."""
    spy.queue("search_read", "maintenance.equipment", [])
    assert processor._buscar_equipo_por_serial(spy, "WE123ABC") == []
    # un solo search_read: el exacto. No hubo fallback.
    assert len(spy.calls_of("search_read", "maintenance.equipment")) == 1


def test_we_solo_no_dispara_fallback(spy):
    """Form 'WE' (sin dígitos) no califica al fallback."""
    spy.queue("search_read", "maintenance.equipment", [])
    assert processor._buscar_equipo_por_serial(spy, "WE") == []
    assert len(spy.calls_of("search_read", "maintenance.equipment")) == 1


# ---------- universo: serials fuera del universo se descartan ---------- #
def test_seriales_fuera_del_universo_se_descartan(spy):
    """Serials que no son .isdigit() ni contienen "WE" no deben contar como match."""
    spy.set_default("search_read", "maintenance.equipment", [
        {"id": 1, "serial_no": "24000"},          # entra (numérica exacta)
        {"id": 2, "serial_no": "ABC24000"},       # fuera del universo (descartar)
        {"id": 3, "serial_no": "we24000"},        # 'we' minúscula → fuera del universo
    ])
    res = processor._buscar_equipo_por_serial(spy, "24000")
    assert len(res) == 1 and res[0]["id"] == 1
