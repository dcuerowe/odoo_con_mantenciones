"""L1 · Unitario — data_processing.check_new_sub (deduplicación SQLite AISLADA).

Cubre TC-TR-01..05 de docs/03_casos_transversales.md.

IMPORTANTE (REQ-ISO-1): check_new_sub calcula la ruta de la DB internamente
(os.path.dirname(__file__)), así que SIEMPRE apunta a form_entries.db real. Estos
tests redirigen sqlite3.connect a una DB temporal vía monkeypatch; nunca tocan la real.
"""

import sqlite3

import pandas as pd
import pytest

import data_processing


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """DB temporal con la tabla processed_entries pre-creada. Redirige
    data_processing.sqlite3.connect hacia ella. Devuelve la ruta."""
    db = tmp_path / "form_entries_test.db"
    real_connect = sqlite3.connect
    con = real_connect(db)
    con.execute("CREATE TABLE processed_entries (entry_id INTEGER PRIMARY KEY)")
    con.commit()
    con.close()
    monkeypatch.setattr(data_processing.sqlite3, "connect",
                        lambda *a, **k: real_connect(db))
    return db, real_connect


def _ids_en_db(db, real_connect):
    con = real_connect(db)
    try:
        return {row[0] for row in con.execute("SELECT entry_id FROM processed_entries")}
    finally:
        con.close()


def test_db_vacia_todo_es_nuevo(temp_db):  # TC-TR-01
    db, rc = temp_db
    res = data_processing.check_new_sub(pd.DataFrame({"#": [9, 10]}))
    assert isinstance(res, pd.DataFrame)
    assert set(res["#"]) == {9, 10}
    assert _ids_en_db(db, rc) == {9, 10}


def test_filtra_los_ya_procesados(temp_db):  # TC-TR-02
    db, rc = temp_db
    con = rc(db)
    con.execute("INSERT INTO processed_entries VALUES (9)")
    con.commit()
    con.close()
    res = data_processing.check_new_sub(pd.DataFrame({"#": [9, 10]}))
    assert isinstance(res, pd.DataFrame)
    assert set(res["#"]) == {10}
    assert _ids_en_db(db, rc) == {9, 10}


def test_nada_nuevo_devuelve_false(temp_db):  # TC-TR-03
    db, rc = temp_db
    con = rc(db)
    con.executemany("INSERT INTO processed_entries VALUES (?)", [(9,), (10,)])
    con.commit()
    con.close()
    res = data_processing.check_new_sub(pd.DataFrame({"#": [9, 10]}))
    assert res is False


def test_tabla_ausente_se_captura(tmp_path, monkeypatch):  # TC-TR-05
    db = tmp_path / "sin_tabla.db"
    real_connect = sqlite3.connect
    real_connect(db).close()  # DB existe pero SIN processed_entries
    monkeypatch.setattr(data_processing.sqlite3, "connect",
                        lambda *a, **k: real_connect(db))
    res = data_processing.check_new_sub(pd.DataFrame({"#": [9]}))
    # El except sqlite3.Error devuelve [] (lista vacía), no DataFrame.
    assert res == []
