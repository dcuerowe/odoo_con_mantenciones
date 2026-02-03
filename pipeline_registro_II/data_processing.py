import pandas as pd
import sqlite3
import traceback
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import os
import re

def ordenar_respuestas(estructura, respuestas):
   # --- 1. Mapeo Recursivo de IDs de preguntas a Títulos ---
    # Es crucial porque las preguntas ahora están dentro de 'group' -> 'questions'
    questions = estructura.get('data', {}).get('questions', [])
    question_id_to_title = {}

    def map_questions(q_list):
        for q in q_list:
            question_id_to_title[q['questionId']] = q['title']
            # Si es un grupo, mirar adentro recursivamente
            if 'questions' in q:
                map_questions(q['questions'])
    
    map_questions(questions)

    # --- 2. Función Auxiliar para extraer valores (La misma lógica robusta) ---
    def extraer_valor(answer_obj):
        # Si no se respondió o está oculta, retornamos None
        if answer_obj.get('wasSubmittedEmpty', False) or answer_obj.get('wasHidden', False):
            return None

        q_type = answer_obj.get('questionType', 'unknown')

        if q_type == 'openEnded':
            return answer_obj.get('value', '')
        elif q_type == 'multipleChoice':
            selected = [opt['text'] for opt in answer_obj.get('selectedAnswers', [])]
            return ', '.join(selected) if selected else ''
        elif q_type == 'yesNo':
             # Ajuste para que '0' sea 'Sí' y '1' sea 'No' según tu historial, o el texto si existe
             idx = answer_obj.get('selectedIndex')
             if idx == 0: return "Sí"
             if idx == 1: return "No"
             return str(idx)
        elif q_type == 'datetime':
            ts = answer_obj.get('timestamp')
            if ts:
                try:
                    dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
                    dt_chile = dt_utc.astimezone(ZoneInfo("America/Santiago"))
                    # Devuelve fecha y hora si existen, o solo fecha
                    return dt_chile.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    return 'Error Fecha'
            return ''
        elif q_type == 'image':
            # Extraer URLs si existen
            imgs = answer_obj.get('images', [])
            return [img.get('url', '') for img in imgs] if imgs else []
        elif q_type == 'signature':
            return "Firma Capturada" if answer_obj.get('images') else "Sin Firma"
        elif q_type == 'rating':
            return answer_obj.get('ratingValue', '')
        elif q_type == 'description':
            return None 
        
        return None # Caso por defecto

    # --- 3. Procesamiento de Submissions ---
    lista_registros = []
    submissions = respuestas.get('data', {}).get('formSubmissions', [])

    for submission in submissions:
        # Datos base de la submission
        ts_envio = submission.get('submissionTimestamp')
        fecha_envio_str = ""
        if ts_envio:
             dt_envio = datetime.fromtimestamp(ts_envio, tz=timezone.utc).astimezone(ZoneInfo("America/Santiago"))
             fecha_envio_str = dt_envio.strftime("%d/%m/%Y %H:%M")

        fila_datos = {
            '#': submission.get('entryNum'),
            'user': submission.get('submittingUserId'),
            'fecha_envio': fecha_envio_str
        }

        # Iterar sobre las respuestas principales
        for answer in submission.get('answers', []):
            q_type = answer.get('questionType')
            q_id = answer.get('questionId')
            
            # --- CASO GROUP (NUEVO) ---
            # El tipo 'group' contiene una lista 'answers' directa, no 'groupAnswers'
            if q_type == 'group' and 'answers' in answer:
                # Iteramos sobre las respuestas DENTRO del grupo
                for ans_anidada in answer['answers']:
                    sub_id = ans_anidada.get('questionId')
                    # Buscamos el título usando el ID (que ya mapeamos recursivamente)
                    titulo = question_id_to_title.get(sub_id, f"Pregunta {sub_id}")
                    
                    val = extraer_valor(ans_anidada)
                    if val is not None:
                        fila_datos[titulo] = val
            
            # --- CASO PREGUNTA NORMAL ---
            else:
                titulo = question_id_to_title.get(q_id, f"Pregunta {q_id}")
                val = extraer_valor(answer)
                if val is not None:
                    fila_datos[titulo] = val

        lista_registros.append(fila_datos)

    # --- 4. Generación del DataFrame ---
    if not lista_registros:
        return pd.DataFrame()

    df_final = pd.DataFrame(lista_registros)
    return df_final

def detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo, modelo, serial, trabajo_id, mensaje):
    """
    Agrega detalles de una operación al diccionario 'resumen', almacenando información relevante en listas asociadas a cada clave.
    """
    resumen['OT'].append(ot)
    resumen['Técnico'].append(tecnico)

    #Transformación de fechas a zona horaria chilena
    dt_utc = datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
    dt_chile = dt_utc.astimezone(ZoneInfo("America/Santiago"))
    fecha_chile = dt_chile.strftime("%Y-%m-%d")
    
    resumen.setdefault('Fecha de revisión', []).append(fecha_chile)
    resumen['Proyecto'].append(proyecto)
    resumen['Punto de monitoreo'].append(punto)
    resumen['Modelo'].append(modelo)
    resumen['N° serie'].append(serial)
    resumen['Tipo'].append(trabajo_id)
    resumen['Equipo/instrumento'].append(tipo)
    resumen['Mensaje'].append(mensaje)

def inbox(ot, id_tecnico, fecha, id_punto, id_tipo, modelo, serial, trabajo_id, odoo_client, mensaje, id_origen, id_etiqueta, etapa):

    origen = {
        'A' : [(4,2)],
        'M' : [(4,1)],
        'N' : [(4,3)]
    }
    
    tipo = {

        'Sonda multiparamétrica': [(4,1)], #Productivo: 1 | Test: 1
        'Sonda Multiparamétrica': [(4,1)], #Productivo: 1 | Test: 1
        'Tablero We': [(4,2)], #Productivo: 2 | Test: 2
        'Tablero': [(4,2)], #Productivo: 2 | Test: 2
        'Otro': [(4,3)], #Productivo: 3 | Test: 4
        'Otro dispositivo crítico': [(4,3)], #Productivo: 3 | Test: 4
        'Caudalímetro': [(4,7)], #Productivo: 7 | Test: 5
        'Caudalímetro Ultrasónico': [(4,4)], #Productivo: 4 | Test: 6
        'Sensor de Nivel': [(4,6)], #Productivo: 6 | Test: 8
        'Caudalímetro Mecánico': [(4,5)] #Productivo: 5 | Test: 7

    }

    carpetas = {
        'MP' : 'https://wetechscl.sharepoint.com/sites/CalidaddelDato/Documentos%20compartidos/Forms/AllItems.aspx?id=%2Fsites%2FCalidaddelDato%2FDocumentos%20compartidos%2F04%2E%20Instalaci%C3%B3n%20y%20Mantenimiento%2FTrazabilidad%20de%20mantenciones%20y%20calibraciones%2FInformes%20de%20mantenci%C3%B3n&viewid=e9007fb8%2Da77d%2D42bb%2D9edb%2D3f9c92e72ff4',
        'MC' : 'https://wetechscl.sharepoint.com/sites/CalidaddelDato/Documentos%20compartidos/Forms/AllItems.aspx?id=%2Fsites%2FCalidaddelDato%2FDocumentos%20compartidos%2F04%2E%20Instalaci%C3%B3n%20y%20Mantenimiento%2FTrazabilidad%20de%20mantenciones%20y%20calibraciones%2FInformes%20de%20mantenci%C3%B3n&viewid=e9007fb8%2Da77d%2D42bb%2D9edb%2D3f9c92e72ff4',
        'CF' : 'https://wetechscl.sharepoint.com/sites/CalidaddelDato/Documentos%20compartidos/Forms/AllItems.aspx?id=%2Fsites%2FCalidaddelDato%2FDocumentos%20compartidos%2F04%2E%20Instalaci%C3%B3n%20y%20Mantenimiento%2FTrazabilidad%20de%20mantenciones%20y%20calibraciones%2FInformes%20de%20mantenci%C3%B3n&viewid=e9007fb8%2Da77d%2D42bb%2D9edb%2D3f9c92e72ff4',
        'I' : 'https://wetechscl.sharepoint.com/sites/CalidaddelDato/Documentos%20compartidos/Forms/AllItems.aspx?id=%2Fsites%2FCalidaddelDato%2FDocumentos%20compartidos%2F04%2E%20Instalaci%C3%B3n%20y%20Mantenimiento%2FTrazabilidad%20de%20mantenciones%20y%20calibraciones%2FInformes%20de%20instalaci%C3%B3n&viewid=e9007fb8%2Da77d%2D42bb%2D9edb%2D3f9c92e72ff4',
        'CI': False
    }

    estados = {
        'Nuevo': 1,
        'En proceso': 2,
        'Resuelto': 4
    }

    etiquetas = {
        'MP sin programar': [(4,1)], #Productivo: 1 | Test: 2
        'Creación en espera': [(4,2)], #Productivo: 2 | Test: 3
        'Cambio de ubicación': [(4,3)], #Productivo: 3 | Test: 4
        'Punto no existe en sistema': [(4,4)], #Productivo: 4 | Test: 5
        'S/N no encontrado': [(4,5)] #Productivo: 5 | Test: 6
    }

    fields_inbox = {
        'x_name': f"OT: {ot}",
        'x_studio_tcnico': id_tecnico,
   
        # 'x_studio_punto_de_monitoreo_1': id_punto,
        'x_studio_punto_de_monitoreo': id_punto,
        
        'x_studio_tipo_de_trabajo': trabajo_id,

        'x_studio_origen': origen[id_origen],
        'x_studio_stage_id': estados[etapa],
        'x_studio_e_i': tipo[id_tipo],
        'x_studio_modelo': modelo,
        'x_studio_nmero_de_serie': serial,

        # 'x_studio_many2many_field_lp8A0': etiquetas[id_etiqueta] if id_etiqueta != False else False,
        'x_studio_etiqueta': etiquetas[id_etiqueta] if id_etiqueta != False else False,

        'x_studio_mensaje': mensaje,
        'x_studio_carpeta': carpetas[trabajo_id],
        'x_studio_fecha_de_ejecucin': fecha
    }

    created_inbox = odoo_client.create(
        'x_inbox_integracion',
        fields_inbox
    )


    #Relacionamos a Emir y a Rodrigo

    # 172: Rodrigo
    # 147: Emir
    follow = odoo_client.message_subscribe(
        'x_inbox_integracion',
        [created_inbox],
        [147, 172 ]
    )

    if id_origen == "M" or id_origen == "N":
        info = odoo_client.message_post(
        'x_inbox_integracion',
        created_inbox,
        f"<b>Caso a ser revisado:</b> {id_etiqueta}")



def check_new_sub(ordered_responses):    
    """
    Procesa una lista de respuestas ordenadas para identificar y registrar nuevas OTs (órdenes de trabajo) en una base de datos SQLite.
    """

    # if not ordered_responses:
    #    print("No se encontraron nuevas OTs para procesar.") 
    #    return
    
    # SE CAMBIA LA FORMA DE GENERAR EL CONJUNTO DE INTERES
    ots = set(ordered_responses["#"])
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
                return False

            # new_entries = [i for i in ordered_responses if i["#"][0] in new_ids]
            
            # SE CAMBIA LA FORMA DE FILTRADO
            new_entries = ordered_responses[ordered_responses["#"].isin(new_ids)]


            # Registrar en la base de datos el ID de las nuevas OT encontradas
            for entry in new_ids:
                cursor.execute("INSERT OR IGNORE INTO processed_entries (entry_id) VALUES (?)", ((entry),))
                print(f"ID {entry} guardado en la base de datos.")
            
            return new_entries
    
    except sqlite3.Error as e:
        print(f'Error en la base de datos: {e}')
        print(traceback.format_exc())
        return []
