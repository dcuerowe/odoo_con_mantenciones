"""L1 · Unitario — data_processing.ordenar_respuestas (función pura, sin red).

Cubre TC-TR-10..17 de docs/03_casos_transversales.md.
ordenar_respuestas(schema, submission) -> DataFrame (1 fila por submission,
columnas = títulos de pregunta).
"""

import data_processing


def _schema(questions):
    return {"data": {"questions": questions}}


def _submission(answers, entry=9, user=42, ts=1700000000):
    return {"data": {"formSubmissions": [{
        "entryNum": entry, "submittingUserId": user,
        "submissionTimestamp": ts, "answers": answers,
    }]}}


def test_openended_y_metadatos_base():
    schema = _schema([{"questionId": "q1", "title": "Nombre del Cliente",
                       "questionType": "openEnded"}])
    sub = _submission([{"questionId": "q1", "questionType": "openEnded", "value": "Aguas X"}])
    df = data_processing.ordenar_respuestas(schema, sub)
    assert df.loc[0, "#"] == 9
    assert df.loc[0, "user"] == 42
    assert df.loc[0, "Nombre del Cliente"] == "Aguas X"


def test_yesno_si_no():  # TC-TR-11
    schema = _schema([{"questionId": "q", "title": "Operativo", "questionType": "yesNo"}])
    df_si = data_processing.ordenar_respuestas(
        schema, _submission([{"questionId": "q", "questionType": "yesNo", "selectedIndex": 0}]))
    df_no = data_processing.ordenar_respuestas(
        schema, _submission([{"questionId": "q", "questionType": "yesNo", "selectedIndex": 1}]))
    assert df_si.loc[0, "Operativo"] == "Sí"
    assert df_no.loc[0, "Operativo"] == "No"


def test_grupo_anidado_aplana_titulos():  # TC-TR-10
    schema = _schema([{
        "questionId": "g1", "title": "Grupo", "questionType": "group",
        "questions": [{"questionId": "q3", "title": "Fecha visita ",
                       "questionType": "datetime"}],
    }])
    sub = _submission([{
        "questionId": "g1", "questionType": "group",
        "answers": [{"questionId": "q3", "questionType": "datetime",
                     "timestamp": 1700000000}],
    }])
    df = data_processing.ordenar_respuestas(schema, sub)
    assert "Fecha visita " in df.columns


def test_datetime_a_santiago():  # TC-TR-12
    schema = _schema([{"questionId": "q", "title": "Fecha", "questionType": "datetime"}])
    # 1700000000 = 2023-11-14 22:13:20 UTC → 19:13:20 en America/Santiago (UTC-3).
    df = data_processing.ordenar_respuestas(
        schema, _submission([{"questionId": "q", "questionType": "datetime",
                              "timestamp": 1700000000}]))
    assert df.loc[0, "Fecha"] == "2023-11-14 19:13:20"


def test_image_devuelve_lista_urls():  # TC-TR-13
    schema = _schema([{"questionId": "q", "title": "Fotos", "questionType": "image"}])
    df = data_processing.ordenar_respuestas(
        schema, _submission([{"questionId": "q", "questionType": "image",
                              "images": [{"url": "a"}, {"url": "b"}]}]))
    assert df.loc[0, "Fotos"] == ["a", "b"]


def test_multiplechoice_join_coma():  # TC-TR-14
    schema = _schema([{"questionId": "q", "title": "Tipos", "questionType": "multipleChoice"}])
    df = data_processing.ordenar_respuestas(
        schema, _submission([{"questionId": "q", "questionType": "multipleChoice",
                              "selectedAnswers": [{"text": "MC"}, {"text": "MP"}]}]))
    assert df.loc[0, "Tipos"] == "MC, MP"


def test_hidden_sin_dato_no_genera_columna():  # TC-TR-15
    # wasHidden + SIN dato real (rama condicional no visitada) -> se descarta.
    schema = _schema([
        {"questionId": "q1", "title": "Visible", "questionType": "openEnded"},
        {"questionId": "q2", "title": "Oculta", "questionType": "openEnded"},
    ])
    sub = _submission([
        {"questionId": "q1", "questionType": "openEnded", "value": "x"},
        {"questionId": "q2", "questionType": "openEnded", "value": "", "wasHidden": True},
    ])
    df = data_processing.ordenar_respuestas(schema, sub)
    assert "Visible" in df.columns
    assert "Oculta" not in df.columns


def test_hidden_con_dato_si_genera_columna():  # TC-TR-15 (contrato fix bf53451)
    # Al editar una submission para cambiar la rama condicional, Connecteam no
    # reevalúa la visibilidad y devuelve casillas ya rellenadas con wasHidden=True.
    # Si hay dato real, la respuesta SE CONSERVA (no se pierde el trabajo del técnico).
    schema = _schema([
        {"questionId": "q1", "title": "Visible", "questionType": "openEnded"},
        {"questionId": "q2", "title": "Oculta con dato", "questionType": "openEnded"},
    ])
    sub = _submission([
        {"questionId": "q1", "questionType": "openEnded", "value": "x"},
        {"questionId": "q2", "questionType": "openEnded", "value": "y", "wasHidden": True},
    ])
    df = data_processing.ordenar_respuestas(schema, sub)
    assert "Oculta con dato" in df.columns
    assert df.loc[0, "Oculta con dato"] == "y"


def test_submission_vacia_da_dataframe_vacio():  # TC-TR-16
    df = data_processing.ordenar_respuestas(_schema([]), {"data": {"formSubmissions": []}})
    assert df.empty
