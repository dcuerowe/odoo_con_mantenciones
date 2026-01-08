import pandas as pd
import sqlite3
import traceback
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os

def ordenar_respuestas(estructura, respuestas):
    # Mapeo de IDs de preguntas a títulos
    question_id_to_title = {q['questionId']: q['title'] for q in estructura['data']['questions']}

    # Lista de DataFrames para almacenar las respuestas
    dfs = []

    # Procesamiento de cada submission
    for submission in respuestas['data']['formSubmissions']:  # Itera sobre cada formulario enviado
        submission_data = {
            '#': submission['entryNum'],  # Guarda el número de entrada (OT)
            'user': submission['submittingUserId']  # Guarda el ID del usuario que envió el formulario
        }
        # Itera sobre cada respuesta dentro del formulario
        for answer in submission.get('answers', []):
            question_id = answer['questionId']  # Obtiene el ID de la pregunta
            # Busca el título de la pregunta usando el ID, si no lo encuentra usa un texto por defecto
            question_title = question_id_to_title.get(question_id, f"Pregunta {question_id}")

            value = None  # Inicializa el valor de la respuesta

            # Solo considerar respuestas que no estén vacías ni ocultas
            if not answer.get('wasSubmittedEpmty', False) and not answer.get('wasHidden', False):
                question_type = answer.get('questionType', 'unknown')  # Obtiene el tipo de pregunta

                # Procesa la respuesta según el tipo de pregunta
                if question_type == 'openEnded':
                    value = answer.get('value', 'error')  # Respuesta de texto libre
                elif question_type == 'multipleChoice':
                    # Une las opciones seleccionadas en una cadena separada por comas
                    selected = [opt['text'] for opt in answer.get('selectedAnswers', [])]
                    value = ', '.join(selected) if selected else 'Ninguna respuesta seleccionada'
                elif question_type == 'yesNo':
                    value = answer.get('selectedIndex', '')  # Índice de respuesta sí/no
                elif question_type == 'datetime':
                    date_sub = answer.get('timestamp', '')  # Obtiene el timestamp
                    dt_utc = datetime.fromtimestamp(date_sub, tz=timezone.utc)  # Convierte a fecha UTC
                    # dt_chile = dt_utc.astimezone(ZoneInfo("America/Santiago"))

                    value = dt_utc.strftime("%Y-%m-%d")  # Formatea la fecha
                elif question_type == 'description':
                    value = None  # Las descripciones no se almacenan   
                elif question_type == 'image':
                    value = answer.get('images', '')  # Obtiene las imágenes adjuntas
                elif question_type == 'signature':
                    value = answer.get('images', '')  # Obtiene las firmas adjuntas
                elif question_type == 'rating':
                    value = answer.get('ratingValue', '')  # Obtiene el valor de la calificación
                else:
                    value = 'Tipo no reconocido'  # Tipo de pregunta no soportado

            # Asocia el valor procesado al título de la pregunta en el diccionario de respuestas
            submission_data[question_title] = value

        # Crea un DataFrame con los datos procesados de la submission
        df = pd.DataFrame([submission_data])
        dfs.append(df)  # Agrega el DataFrame a la lista

    return dfs  # Devuelve la lista de DataFrames

def detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo, modelo, serial, trabajo_id, mensaje):
    """
    Agrega detalles de una operación al diccionario 'resumen', almacenando información relevante en listas asociadas a cada clave.
    """
    resumen['OT'].append(ot)
    resumen['Técnico'].append(tecnico)
    resumen.setdefault('Fecha de revisión', []).append(fecha)
    resumen['Proyecto'].append(proyecto)
    resumen['Punto de monitoreo'].append(punto)
    resumen['Modelo'].append(modelo)
    resumen['N° serie'].append(serial)
    resumen['Tipo'].append(trabajo_id)
    resumen['Equipo/instrumento'].append(tipo)
    resumen['Mensaje'].append(mensaje)

def check_new_sub(ordered_responses):    
    """
    Procesa una lista de respuestas ordenadas para identificar y registrar nuevas OTs (órdenes de trabajo) en una base de datos SQLite.
    """

    if not ordered_responses:
       print("No se encontraron nuevas OTs para procesar.") 
       return
    
    ots = (df['#'][0] for df in ordered_responses)
    ots_id = {int(i) for i in ots}

    # 1. Obtener la ruta absoluta del directorio donde está ESTE script (main.py)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # 2. Construir la ruta completa a la base de datos
    db_path = os.path.join(BASE_DIR, 'form_entries.db')
    
    try:
        with sqlite3.connect(db_path) as connection:
            cursor = connection.cursor()

            # --- BLOQUE DE DEBUG: LISTAR TABLAS ---
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tablas = cursor.fetchall()
            
            # ---------------------------------------

            # Creamos placeholders (?,?,?) para una consulta segura
            if ots_id:
                placeholders = ','.join(['?'] * len(list(ots_id)))
                query = f"SELECT entry_id FROM processed_entries WHERE entry_id IN ({placeholders})"
                cursor.execute(query, tuple(ots_id))
                # El resultado es una lista de tuplas (e.g., [(101,), (102,)]), las convertimos a un set.
                processed_ids = {row[0] for row in cursor.fetchall()}
            else:
                processed_ids = set()
    

            # Comparar para encontrar solo lo nuevo
            new_ids = ots_id - processed_ids
            if not new_ids:
                print("No hay nuevas OTs para procesar.")
                return

            new_entries = [i for i in ordered_responses if i["#"][0] in new_ids]

            # Registrar en la base de datos el ID de las nuevas OT encontradas
            for entry in new_entries:
                cursor.execute("INSERT OR IGNORE INTO processed_entries (entry_id) VALUES (?)", (int(entry['#'][0]),))
                print(f"ID {entry['#'][0]} guardado en la base de datos.")
            
            return new_entries
    
    except sqlite3.Error as e:
        print(f'Error en la base de datos: {e}')
        print(traceback.format_exc())
        return []
