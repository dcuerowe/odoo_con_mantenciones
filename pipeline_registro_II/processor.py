import re
import base64
import traceback
import pandas as pd
from datetime import datetime
from connecteam_api import user
from data_processing import detalle_op, inbox
from report_generator import informe_pdf_profesional
from config import SHAREPOINT_UPLOAD_BASE_URL, SHAREPOINT_UPLOAD_INSTALL_BASE_URL



def process_entrys(ordered_responses, API_key_c, resumen, exito, odoo_client, sharepoint_client):

    for i, r in ordered_responses.iterrows():

        r_clean = r.dropna()
        
        df = r_clean.to_frame().T #Transformamos la serie en un dataframe

        df_columnas = df.columns.to_list() #Lista de columnas que si tienen datos

        # df = df.astype({'user': str}) #Dejamos al id del user como string
        index_user = df.columns.get_loc('user') #Obtenemos la posición de la columna user

        try:
            user_name = user(API_key_c, df.iloc[0, index_user])
        except Exception as e:
            user_name = "Usuario no encontrado"
            print(f"Error al obtener el nombre del usuario: {e}")
            traceback.print_exc()
        
        try:
            df.iloc[0, index_user] = user_name # Añadir el nombre del usuario al DataFrame
        except Exception as e:
            print(f"Error al asignar el nombre del usuario al DataFrame: {e}")
            traceback.print_exc()


        #Elementos globales
        id_tipo_de_trabajo = ['MP', 'MC', 'I', 'CI', 'CF']

        #Consideraciones para 
        MP_type = ['T', 'I']
        MP_translate = {
            'I': 'Dispositivo',
            'T': 'Tablero'
        }


        I_type = ['I', 'T'] 
        I_translate = {
            'I': 'dispositivo',
            'T': 'tablero'
        }
        
        id_mantencion = {'MC': 'Mantención Correctiva',
                        'MP': 'Mantención Preventiva',
                        'I': 'Instalación',
                        'CI': 'Calibración',
                        'CF': 'Configuración'}
        
        # intalaciones_interes = ['Tablero', 'Caudalímetro', 'Sensor de nivel', 'Sonda multiparamétrica', 'Otro']

        #Identificador de ususarios en el modelo de contactos
        operators ={
            "Diego Marchant": 145,
            "Ángel Zamora": 181,
            "Camilo Sandoval": 138,
            "Cristopher Iglesias": 141,
            "David  Loncopan": 144,
            "Emir Navarro Crocci": 147,
            "Felipe Riquelme": 149,
            "Juan José López": 159,
            "Leonardo Gonzalez": 160,
            "Matías Pomar": 164,
            "Rodrigo López": 172,
            "Tomás Bustamante": 178,
            "Elías Sanchez": 5432
        }

        #Puntos que efectivamente se visitaron
        numeros_visita = set()
        for col in df_columnas:
            # Verificamos si el nombre de la columna comienza con un dígito
            if col and col[0].isdigit():
                # Extraemos el primer carácter (el número)
                numeros_visita.add(col[0])

        numeros_visita = sorted(list(numeros_visita))
        
        for i in numeros_visita:

            #Separación de los trabajos realizados
            try: 
                tipos_realizados = [tipo.strip() for tipo in df[f'{i}.2 Tipo de trabajo a realizar'].iloc[0].split(',') ]
            except:
                tipos_realizados = df[f'{i}.2 Tipo de trabajo a realizar']
                

            # Columnas del punto {1} | general
            columnas_visita = [columna for columna in df_columnas if columna.startswith(i)]
            #columnas_visita.append(f'{i} Proyecto') 
            columnas_visita = ['#', 'user', 'Fecha visita ', 'Nombre del Cliente'] + columnas_visita 
            
            #Dejando un dataframe a nivel de visita de punto
            df_visita = df[columnas_visita].copy()


            #Validando si el punto se encuentra seteadao en el listado de connecteam
            if df_visita[f'{i}.1 Punto de monitoreo'].iloc[0] == "No encontrado":
            
                #Creamos la columna proyecto
                try:
                    index_columna_punto_proyecto = df_visita.columns.get_loc(f'{i} Proyecto')
                    df_visita.loc[:, f"{i}.1 Proyecto"] = df_visita.iloc[0, index_columna_punto_proyecto]
                    
                    #Definimos el punto ingresado manaualmente como el verdadero
                    index_columna_punto_no = df_visita.columns.get_loc(f'{i}.1 Punto de monitoreo')
                    index_columna_punto_si = df_visita.columns.get_loc(f'{i}.1 Indicar nombre del punto')

                    df_visita.iloc[0, index_columna_punto_no] = df_visita.iloc[0, index_columna_punto_si]

                    del df_visita[f'{i}.1 Indicar nombre del punto']
                except Exception as e:
                    print(f"Error al procesar el punto de monitoreo en OT {df_visita['#']}: {e}")
                    # Si no se encuentra la columna, asignamos un valor por defecto
                    df_visita.loc[:, f"{i}.1 Proyecto"] = "Proyecto no especificado"
                    df_visita.loc[:, f"{i}.1 Punto de monitoreo"] = "Punto no especificado"
                    continue
                    

            else:
                #Buscando el indice de columna
                index_columna_punto = df_visita.columns.get_loc(f'{i}.1 Punto de monitoreo')

                #Definiendo el nombre del proyecto
                match = re.search(r"\[([^\]]*)\]", df_visita.iloc[0, index_columna_punto])
                if match:
                    df_visita.loc[:, f"{i}.1 Proyecto"] = match.group(1)
                else:
                    df_visita.loc[:, f"{i}.1 Proyecto"] = "Proyecto no especificado"
                                
                #Definiedo el nombre del punto
                df_visita.iloc[0, index_columna_punto] = re.sub(r"\[[^\]]*\]", "", df_visita.iloc[0, index_columna_punto]).strip() #Eliminando el nombre del proyecto



            #Definimos los ID de los tipos de trabajo realizados
            id_tipos_realizados = [item.split(' |')[0] for item in tipos_realizados]
            #id_tipos_realizados

            #Definimos el listaod de imagenes

            #Definimos los ID de tipos de trabajo de interes
            id_tipos_interes = []
            for tipo in id_tipos_realizados:
                if tipo in id_tipo_de_trabajo:
                    id_tipos_interes.append(tipo)
            id_tipos_interes #[MC, MP]
            
            #Cantidad de MP realizadas

            #Conteo de instalaciones de instrumentos
            I_I_prefijo = set()
            for col in df_visita.columns:
                if ' I (I) |' in col: 
                    # Extraemos el prefijo como '1.2.1 MP' o '1.2.2 MP'
                    prefix_end_index = col.find(' I (I) |') + 4 # Sumamos 4 para incluir ' MP'
                    prefix = col[:prefix_end_index].strip()
                    I_I_prefijo.add(prefix)
            
            conteo_instancias_I_I = len(I_I_prefijo)
        
            #Conteo en el contesto de los tableros
            I_T_prefijo = set()
            for col in df_visita.columns:
                if ' I (T) |' in col: 
                    # Extraemos el prefijo como '1.2.1 MP' o '1.2.2 MP'
                    prefix_end_index = col.find(' I (T) |') + 4 # Sumamos 4 para incluir ' MP'
                    prefix = col[:prefix_end_index].strip()
                    I_T_prefijo.add(prefix)
            
            conteo_instancias_I_T = len(I_T_prefijo)

            conteo_I = {
                'I': conteo_instancias_I_I,
                'T': conteo_instancias_I_T
            }

            #Conteo en el contexto de los instrumentos
            MP_I_prefijo = set()
            for col in df_visita.columns:
                if ' MP (I) |' in col: 
                    # Extraemos el prefijo como '1.2.1 MP' o '1.2.2 MP'
                    prefix_end_index = col.find(' MP (I) |') + 4 # Sumamos 4 para incluir ' MP'
                    prefix = col[:prefix_end_index].strip()
                    MP_I_prefijo.add(prefix)
            
            conteo_instancias_MP_I = len(MP_I_prefijo)
        
            #Conteo en el contesto de los tableros
            MP_T_prefijo = set()
            for col in df_visita.columns:
                if ' MP (T) |' in col: 
                    # Extraemos el prefijo como '1.2.1 MP' o '1.2.2 MP'
                    prefix_end_index = col.find(' MP (T) |') + 4 # Sumamos 4 para incluir ' MP'
                    prefix = col[:prefix_end_index].strip()
                    MP_T_prefijo.add(prefix)
            
            conteo_instancias_MP_T = len(MP_T_prefijo)

            conteo_MP = {
                'I': conteo_instancias_MP_I,
                'T': conteo_instancias_MP_T
            }

            #Cantidad de MC realizadas
            MC_prefijo = set()
            for col in df_visita.columns:
                if ' MC |' in col: # Buscamos ' MC |' para identificar las columnas de MC
                    # Extraemos el prefijo como '1.2.1 MC' o '1.2.2 MC'
                    prefix_end_index = col.find(' MC |') + 4 # Sumamos 4 para incluir ' MC'
                    prefix = col[:prefix_end_index].strip()
                    MC_prefijo.add(prefix)
                    
            conteo_instancias_MC = len(MC_prefijo)
            


            #Cantidad de CF realizadas
            CF_prefijo = set()
            for col in df_visita.columns:
                if ' CF |' in col: # Buscamos ' CF |' para identificar las columnas de CF
                    # Extraemos el prefijo 
                    prefix_end_index = col.find(' CF |') + 4 # Sumamos 4 para incluir ' CF'
                    prefix = col[:prefix_end_index].strip()
                    CF_prefijo.add(prefix)
                    
            conteo_instancias_CF = len(CF_prefijo)


            #Cantidad de CI realizadas
            CI_prefijo = set()
            for col in df_visita.columns:
                if ' CI |' in col: # Buscamos ' CI |' para identificar las columnas de CI
                    # Extraemos el prefijo 
                    prefix_end_index = col.find(' CI |') + 4 # Sumamos 4 para incluir ' CI'
                    prefix = col[:prefix_end_index].strip()
                    CI_prefijo.add(prefix)
                    
            conteo_instancias_CI = len(CI_prefijo)

            #Imagenas
            
            lista_imagenes = df_visita[f'{i}.4 Fotos recinto'].to_list()[0]

            #Observaciones generales

            obs_generales = df_visita[f'{i}.3 Resolución de visita'].to_list()[0]

            #Variables globales del punto visitado
            proyecto = df_visita[f"{i}.1 Proyecto"].to_list()[0]
            punto = df_visita[f'{i}.1 Punto de monitoreo'].to_list()[0]
            ot = df_visita['#'].to_list()[0]
            fecha = df_visita['Fecha visita '].to_list()[0]
            tecnico = df_visita['user'].to_list()[0].strip()
            cliente = df_visita['Nombre del Cliente'].to_list()[0]
            
            

            # print(df_visita)
            # print(columnas_capa_punto)
            for id in id_tipos_realizados:
                #Iniciamos la filtración por tipos de trabajo
                columnas_trabajo = [columna for columna in df_visita.columns if f'{id}' in columna]

                columnas_trabajo = ['#', 'user', f"{i}.1 Proyecto", 'Fecha visita ', 'Nombre del Cliente'] + columnas_trabajo
                df_trabajo = df_visita[columnas_trabajo]

                #Tratamiento para Mantención correctiva
                if id == "MC":
                    for equipo in range(1, conteo_instancias_MC+1):
                        filtro_MC = f"{i}.2.{equipo} MC"        
                        columnas_equipo_MC = df_trabajo.filter(like=filtro_MC).columns.to_list()
                        columnas_equipo_MC = ['#', 'user', f"{i}.1 Proyecto", 'Fecha visita ', 'Nombre del Cliente'] + columnas_equipo_MC
                        
                        #df trabajo se usa para la generación del informe
                        df_trabajo_equipo_MC = df_trabajo[columnas_equipo_MC]
                        dic_trabajo_MC = df_trabajo_equipo_MC.to_dict(orient='records')[0]

                        #Elmentos propios del equipo
                        modelo_MC = dic_trabajo_MC[f"{i}.2.{equipo} MC | Modelo"]
                        tipo_MC = dic_trabajo_MC[f"{i}.2.{equipo} MC | Activo a intervenir"]
                        serial_MC = dic_trabajo_MC[f'{i}.2.{equipo} MC | N° de serie']
                        operativo_MC = dic_trabajo_MC[f"{i}.2.{equipo} MC | ¿Equipo operativo tras trabajos?"]
                        obs_MC = dic_trabajo_MC[f'{i}.2.{equipo} MC | Observación']

                        print(dic_trabajo_MC)
                        
                        #Asegurando que el serial pase de float a int
                        for llave, valor in dic_trabajo_MC.items():
                                    if isinstance(valor,float):
                                        dic_trabajo_MC[llave] = int(valor)


                        pdf_stream_MC = informe_pdf_profesional(i, ot, tecnico, proyecto, fecha, cliente, tipo_MC, modelo_MC, serial_MC, id, False, punto, obs_MC, obs_generales, lista_imagenes, equipo)
                        
                        nombre_archivo_MC = f"informe_OT-{ot}_{i}_{id}_{equipo}.pdf"

                        pdf_stream_MC.seek(0)

                        try:
                            contenido_pdf = pdf_stream_MC.read()
                            informe_codificado_MC = base64.b64encode(contenido_pdf).decode('utf-8')
                        except FileNotFoundError:
                            exit()


                        #------------------------------------------------------------------------
                        #Busqueda del ID del equipo en la base de datos maintenance.equipment
                        try:
                            equipment_MC = odoo_client.search_read(
                                'maintenance.equipment',
                                [['serial_no', '=', serial_MC]],
                                limit=1
                            )

                            if equipment_MC:

                                #Validamos la ubicación del equipo:
                                id_number_MC = equipment_MC[0]['id']
                                
                                if equipment_MC[0]['x_studio_location']:
                                    location_MC = equipment_MC[0]['x_studio_location'][1]
                                else:
                                    location_MC = False

                                puntos_odoo = odoo_client.search_read(
                                    'x_maintenance_location',
                                    [],
                                    fields=['id', 'x_name']
                                )
                                #Lista de diccionarios

                                id_punto = None
                                for p in puntos_odoo:
                                    if p['x_name'] == f'[{proyecto}] {punto}':
                                        id_punto = p['id']
                                        break

                                if not id_punto:
                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id, 
                                            f'{punto} no se encuentra listado en Odoo y Connecteam')
                                    
                                    inbox(ot, operators[tecnico], fecha, False, tipo_MC, modelo_MC, serial_MC, id, odoo_client,
                                            f'{punto} no se encuentra listado en Odoo y Connecteam. Solicitar creación',
                                            'M',
                                            'Punto no existe en sistema',
                                            'Nuevo')

                                
                                #Equipo a reparar sin una instancia de instalación

                                if location_MC == False:

                                    try:
                                        star_location = odoo_client.message_post(
                                            'maintenance.equipment',
                                            number_equipment_MC,
                                            f"<p><b>Equipo sin evento de instalación We.</b></p><<p>Ubicación actual según OT-{ot}: {punto}</p>"
                                        )

                                        #trabajos sobre equipos que no estan con punto asignado
                                        inbox(ot, operators[tecnico], fecha, id_punto, 'Sonda multiparamétrica', modelo_MC, serial_MC, id, odoo_client,
                                            f'Equipo sin evento de instalación We en el punto {punto}. Validar {nombre_archivo_MC}',
                                            'N',
                                            'Cambio de ubicación',
                                            'En proceso')
                                    
                                    except Exception as e:
                                        print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')
                    

                                elif location_MC != f'[{proyecto}] {punto}':
                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, 'Sonda multiparamétrica', modelo_MC, serial_MC, id, 
                                                f'Equipo pasa de {location_MC} a {punto}). Validar cambio')
                                    
                                    #Notificación por cambio de ubicación

                                    try:
                                        
                                        new_location_MC = odoo_client.message_post(
                                            'maintenance.equipment',
                                            number_equipment_MC,
                                            f"<p><b>La ubicación a cambiado.</b></p><p><b>Nueva ubicación según OT-{ot}:</b> {location_MC} => [{proyecto}] {punto}</p>"
                                        )

                                        inbox(ot, operators[tecnico], fecha, id_punto, 'Sonda multiparamétrica', modelo_MC, serial_MC, id, odoo_client,
                                                f'Equipo pasa de {location_MC} a {punto}). Validar {nombre_archivo_MC}',
                                                'N',
                                                'Cambio de ubicación',
                                                'En proceso')
                                                

                                    except Exception as e:
                                        print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}') 
                                
                                try:
                                    domain_filter_MC = [['equipment_id', '=', id_number_MC],
                                                    ['maintenance_type', '=', 'corrective'],
                                                    ['x_studio_tipo_de_trabajo', '=', 'Mantención Correctiva']] #Productivo: x_studio_tipo_trabajo

                                    request_ids_MC = odoo_client.search(
                                        'maintenance.request',
                                        domain_filter_MC
                                    )
                                    
                                    #Validación de si se programo o no el trabajo
                                    interruptor_MC = True    
                                    for ids_MC in request_ids_MC:
                                        campos_de_interes_MC = ['schedule_date', 'stage_id', "name"]
                                        try:
                                            request_data_MC = odoo_client.read(
                                                'maintenance.request',
                                                [ids_MC],
                                                fields=campos_de_interes_MC
                                            )
                                            
                                            stage_id_MC = request_data_MC[0].get('stage_id') 
                                            schedule_date_MC = request_data_MC[0].get('schedule_date')
                                            # Elementos sin fecha programada
                                            if schedule_date_MC == False:
                                                continue
                                            # Elementos con fecha programada y en estado finalizado
                                            elif schedule_date_MC != False and stage_id_MC[0] == 5:
                                                continue
                                            # Elementos con fecha programada y en estado de desecho
                                            elif schedule_date_MC != False and stage_id_MC[0] == 4:
                                                continue
                                            else:
                                                interruptor_MC = False
                                                break
                                        except Exception as e:
                                            print(e)

                                     #------------------------------------------------------------------------

                                    #Creación de request
                                    if interruptor_MC:
                                        
                                        if operativo_MC == 'No':
                                            try:
                                                fields_values_OT_MC = {
                                                    'name': f"Mantenimiento Correctivo | {tipo_MC} {modelo_MC}",
                                                    'equipment_id': id_number_MC, #Aquí debemos usar el ID númerico de la sonda
                                                    'stage_id': '3', # 3 En proceso 
                                                    'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                    # 'x_studio_etiqueta_1': id_mantencion[id],
                                                    'schedule_date': f"{fecha}",
                                                    'description': obs_MC
                                                }

                                                created_request_MC = odoo_client.create(
                                                    'maintenance.request',
                                                    fields_values_OT_MC
                                                )
                                                
                                                #Resgistro en resumen
                                                detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id,
                                                            f'Se crea con éxito el registro de mantenimiento {created_request_MC}')

                                                inbox(ot, operators[tecnico], fecha, id_punto, tipo_MC, modelo_MC, serial_MC, id, odoo_client,
                                                        'Se crea con éxito el registro de mantenimiento',
                                                        'A',
                                                        False,
                                                        'Resuelto')
                                        
                                                  
                                                attachment_MC = odoo_client.create(
                                                    "ir.attachment",
                                                    {
                                                        "name": nombre_archivo_MC,
                                                        #"type": "binary",
                                                        "datas": informe_codificado_MC,
                                                        "res_model": 'maintenance.equipment',
                                                        "res_id": created_request_MC,
                                                        "mimetype": "application/pdf",
                                                    }
                                                )

                                                current_location_MC = odoo_client.message_post(
                                                    'maintenance.request',
                                                    created_request_MC,
                                                    f"<p><b>Ultima ubicación:</b> {punto}</p><p><b>Ejecutor:</b> {tecnico}</p>",
                                                    attachment_ids=[attachment_MC]
                                                )

                                                
                                                #Actualización de bitácora

                                            except Exception as e:
                                                print(f"Error al crear request MC para la OT-{dic_trabajo_MC['#']} en Odoo: {type(e)}")
                                                print(traceback.format_exc())
                                                continue

                                        # Se realiza el trabajo y queda operativo el dispositivo
                                        elif operativo_MC == 'Sí':
                                            try:
                                                fields_values_OT_MC = {
                                                    'name': f"Mantenimiento Correctivo | {tipo_MC} {modelo_MC}",
                                                    'equipment_id': id_number_MC, #Aquí debemos usar el ID númerico de la sonda
                                                    'stage_id': '5', # 5 Finalizado
                                                    'description': f"{obs_MC}",
                                                    'schedule_date': f"{fecha}",
                                                    'x_studio_informe': informe_codificado_MC,
                                                    'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                    # 'x_studio_etiqueta_1': id_mantencion[id],

                                                }
                                                created_request_MC = odoo_client.create(
                                                    'maintenance.request',
                                                    fields_values_OT_MC
                                                )

                                                #Hacemos la escritura para que se actualice la fecha de cierre
                                                update_stage_MC = {
                                                    'stage_id': 5,
                                                }

                                                update_stage_MC = odoo_client.write(
                                                    'maintenance.request',
                                                    [created_request_MC], 
                                                    update_stage_MC
                                                )

                                                update_close_date_MC = {
                                                    'close_date': fecha,
                                                    'x_studio_tcnico': operators[tecnico]
                                                }

                                                update_close_date_MC = odoo_client.write(
                                                    'maintenance.request',
                                                    [created_request_MC], 
                                                    update_close_date_MC
                                                )

                                                #Resgistro en resumen
                                                detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id,
                                                            f'Se crea con éxito el registro de mantenimiento {created_request_MC}')

                                                inbox(ot, operators[tecnico], fecha, id_punto, tipo_MC, modelo_MC, serial_MC, id, odoo_client,
                                                    'Se crea con éxito el registro de mantenimiento',
                                                    'A',
                                                    False,
                                                    'Resuelto')

                                                
                                                
                                                #Actualización de la actividad por defecto 'Maintenance Request'
                                                #Buscando el ID de la OT creada
                                                id_MC = odoo_client.search(
                                                    'maintenance.request',
                                                    [['id', '=', created_request_MC]],
                                                    limit=1
                                                )
                                                
                                                try:
                                                    #Buscamos el ID de la actividad existente para la OT_number
                                                    actividad_id_MC = odoo_client.search_read(
                                                        'mail.activity',
                                                        [['res_model', '=', 'maintenance.request'], ['res_id', '=', created_request_MC]],
                                                        limit=1
                                                    )

                                                    #Actualizando actividad
                                                    try:
                                                        actividad_number_MC = actividad_id_MC[0]['id']
                                                        odoo_client.action_feedback(
                                                            'mail.activity',
                                                            [actividad_number_MC],
                                                            f"<p><b>Se ha completado desde API</b></p><p>Última ubicación: {punto}</p>"
                                                        )

                                                    except Exception as e:
                                                        print(f"Error al actualizar la actividad de mantenimiento asociada: {e}")
                                                        continue        
                                                    
                                                except Exception as e:
                                                    print(f"Error al buscar la actividad de manteniminto asociada: {e}") 
                                                    continue   

                                        
                                            except Exception as e:
                                                print(f"Error al crear request MC para la OT-{dic_trabajo_MC['#']} en Odoo: {type(e)}")
                                                print(traceback.format_exc())
                                                continue

#                                         elif operativo_MC == 'Irrecuperable':
                                    
#                                             try:
#                                                 fields_values_OT_MC = {
#                                                     'name': f"Mantenimiento Correctivo | {tipo_MC} {modelo_MC}",
#                                                     'equipment_id': id_number_MC, #Aquí debemos usar el ID númerico de la sonda
#                                                     'stage_id': '4', # 4 Desechar
#                                                     'maintenance_type': id_mantencion[id],
#                                                     'schedule_date': f"{dic_trabajo_MC[f'Fecha visita ']}",
#                                                     'x_studio_informe': informe_codificado_MC,
                                                    
#                                                     # 'maintenance_team_id': 1, #Equipo de mantenimiento por defecto
#                                                     # 'user_id':  #Asignando el técnico que creó la solicitud
#                                                 }
#                                                 created_request_MC = odoo_client.create(
#                                                     'maintenance.request',
#                                                     fields_values_OT_MC
#                                                 )
                                                
#                                                 #Hacemos la escritura para que se actualice la fecha de cierre
#                                                 update_stage_MC = {
#                                                     'stage_id': 4,
#                                                 }

#                                                 update_stage_MC = odoo_client.write(
#                                                     'maintenance.request',
#                                                     [created_request_MC], 
#                                                     update_stage_MC
#                                                 )


#                                                 #Resgistro en resumen
#                                                 detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id,
#                                                             f'Se crea con éxito el registro de mantenimiento {created_request_MC}')
                                                
#                                                 try:    
#                                                     #Actualización de la actividad por defecto 'Maintenance Request'
#                                                     #Buscando el ID de la OT creada
#                                                     # Aca debemos incluir la gestión de estados a los dispositivos
#                                                     # - Activo: Validado con el evento de intalación
#                                                     # - Inactivo: Estado por defecto, hasta que no se concrete la instalación
#                                                     # - Mantención: Siempre que mantenga algún mantenimento en estado 'En Proceso'
#                                                     # - Desechado: Siempre que mantenga algún mantenimiento en estado 'Desechar'
                                                    
#                                                     #Buscamos el ID de la actividad existente para la OT_number
#                                                     actividad_id_MC = odoo_client.search_read(
#                                                         'mail.activity',
#                                                         [['res_model', '=', 'maintenance.request'], ['res_id', '=', created_request_MC]],
#                                                         limit=1
#                                                     )

#                                                     #Actualizando actividad
#                                                     try:
#                                                         actividad_number_MC = actividad_id_MC[0]['id']
#                                                         odoo_client.action_feedback(
#                                                             'mail.activity',
#                                                             [actividad_number_MC],
#                                                             "<b>Equipo dado de baja</b>"
#                                                         )

#                                                     except Exception as e:
#                                                         print(f"Error al actualizar la actividad de mantenimiento asociada: {e}")
#                                                         continue        
                                                    
#                                                 except Exception as e:
#                                                     print(f"Error al buscar la actividad de manteniminto asociada: {e}") 
#                                                     continue 

                                                    
#                                                     id_MC = odoo_client.search(
#                                                         'maintenance.request',
#                                                         [['id', '=', created_request_MC]],
#                                                         limit=1
#                                                     ) 
                                                   
#                                                 except Exception as e:
#                                                     print(f"Error al buscar request de mantenimiento recien creada: {e}")
#                                                     continue

#                                                 #Actualización de bitácora

#                                             except Exception as e:
#                                                 print(f"Error al crear request MC para la OT-{dic_trabajo_MC['#']} en Odoo: {type(e)}")
#                                                 print(traceback.format_exc())
#                                                 continue
#                                         """


#                                     #------------------------------------------------------------------------
#                                     #Actualización del request encontrado
#                                     """
                                    else:

                                        if operativo_MC == "Sí":
                                            try:
                                                #Atualizando su estado a Finalizado
                                                update_MC = {
                                                    'stage_id': 5,
                                                    'x_studio_informe': informe_codificado_MC,
                                                }

                                                update_stage_MC = odoo_client.write(
                                                    'maintenance.request',
                                                    [ids_MC], 
                                                    update_MC
                                                )

                                                close_date_MC = {
                                                        'close_date': fecha
                                                }
                                                
                                                update_close_date_MC = odoo_client.write(
                                                    'maintenance.request',
                                                    [ids_MC], 
                                                    close_date_MC
                                                )

                                                if update_stage_MC:
                                                    detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id, 
                                                                f'Se registra con exito el mantenimiento correctivo pendiente: {ids_MC}')
                                                    
                                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_MC, modelo_MC, serial_MC, id, odoo_client,
                                                        'Se registra con éxito el registro de mantenimiento',
                                                        'A',
                                                        False,
                                                        'Resuelto')
                                                    
                                                    #Actualización de bitácora
                                                    try:
                                                        actividad_id_MC = odoo_client.search_read(
                                                            'mail.activity',
                                                            [['res_model', '=', 'maintenance.request'], ['res_id', '=', ids_MC]],
                                                            limit=1
                                                        )
                                                        
                                                        #Actualizando actividad
                                                        if actividad_id_MC:
                                                            try:
                                                                actividad_number_MC = actividad_id_MC[0]['id']
                                                                odoo_client.action_feedback(
                                                                    'mail.activity',
                                                                    [actividad_number_MC],
                                                                    f"<p><b>Se ha completado desde API</b></p><p>Última ubicación: {punto}</p>"
                                                                )
                                                                
                                                            except Exception as e:
                                                                print(f"Error al actualizar estado de la actividad de mantenimiento: {e}")

                                                    except Exception as e:
                                                        print(f"Error al listar de la actividad de mantenimiento: {e}")
                                            
                                                    #  Buscamos el ID de la actividad existente para la OT
                                                            
                                            except Exception as e:
                                                print(f"Error al actualizar estado de solicitud de mantenimiento MC: {e}")
                                                traceback.print_exc()
                                                continue
                                        
                                        #Actualizamos el estado de la solicitud cuando el trabajo no deja el equipo operativo
                                        elif operativo_MC == "No":
                                            try:
                                                #Atualizando su estado a en proceso
                                                update_MC = {
                                                    'stage_id': 3,
                                                }

                                                update_stage_MC = odoo_client.write(
                                                    'maintenance.request',
                                                    [ids_MC], 
                                                    update_MC
                                                )   

                                                if update_stage_MC:
                                                    detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id, 
                                                                f'Se registra con exito el mantenimiento correctivo pendiente: {ids_MC}')

                                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_MC, modelo_MC, serial_MC, id, odoo_client,
                                                        'Se registra con éxito el registro de mantenimiento',
                                                        'A',
                                                        False,
                                                        'Resuelto')
                                                
                                                    attachment_MC = odoo_client.create(
                                                        "ir.attachment",
                                                        {
                                                            "name": nombre_archivo_MC,
                                                            #"type": "binary",
                                                            "datas": informe_codificado_MC,
                                                            "res_model": 'maintenance.equipment',
                                                            "res_id": ids_MC,
                                                            "mimetype": "application/pdf",
                                                        }
                                                    )

                                                    current_location_MC = odoo_client.message_post(
                                                        'maintenance.request',
                                                        ids_MC,
                                                        f"<p><b>Ultima ubicación:</b> {punto}</p><p><b>Ejecutor:</b> {dic_trabajo_MC['user']}</p>",
                                                        attachment_ids=[attachment_MC]
                                                    )
                                            except Exception as e:
                                                print(f"Error al actualizar estado de solicitud de mantenimiento MC: {e}")
                                                traceback.print_exc()
                                                continue                      
                                    
                                except Exception as e:
                                    print(f"Error al buscar las solicitudes de mantenimiento: {e}")
                                    continue
                                
                            else:
                                try:
                                    sharepoint_client.upload_file(f'{SHAREPOINT_UPLOAD_BASE_URL}/{nombre_archivo_MC}:/content', pdf_stream_MC, "application/pdf" )
                                except Exception as e:
                                    print(f"Error al subir el informe al Sharepoint: {e}")

                                detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id, 
                                            f'N° de serie no encontrado en Odoo. Revisar OT | {nombre_archivo_MC}')
                                

                                punto_odoo = odoo_client.search_read(
                                    'x_maintenance_location',
                                    [['x_name', '=', f'[{proyecto}] {punto}']],
                                    limit=1
                                )
                                
                                
                                id_punto = punto_odoo[0]['id']


                                if not id_punto:
                                    id_punto = False
                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id, 
                                            f'{punto} no se encuentra listado en Odoo y Connecteam')

                                    inbox(ot, operators[tecnico], fecha, False, tipo_MC, modelo_MC, serial_MC, id, odoo_client,
                                            f'{punto} no se encuentra listado en Odoo y Connecteam. Solicitar creación',
                                            'M',
                                            'Punto no existe en sistema',
                                            'Nuevo')

                                domain = [
                                    ('location_usage', '=', 'transit'),
                                    ('location_dest_usage', '=', 'customer'),
                                    ('lot_id.name', '=', serial_MC),
                                    # ('reference', '=', 'WH/OUT/00189'),
                                    ('state', 'not in', ['done', 'cancel'])  # Filtra para que NO sea 'done' ni 'cancel'
                                ]

                                search_read = odoo_client.search_read(
                                    'stock.move.line',
                                    domain,
                                    limit=1
                                )


                                if search_read:
                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_MC, modelo_MC, serial_MC, id, odoo_client,
                                            f'N° de serie no encontrado en Odoo. Revisar OT | {nombre_archivo_MC}',
                                            'M',
                                            'Creación en espera',
                                            'Nuevo')
                                else:
                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_MC, modelo_MC, serial_MC, id, odoo_client,
                                            f'N° de serie no encontrado en Odoo. Revisar OT | {nombre_archivo_MC}',
                                            'M',
                                            'S/N no encontrado',
                                            'Nuevo')

                                
                        except Exception as e:
                            print(f"Error al buscar equipo en base de Odoo MC: {e}")
                            continue

                #Tratamiento para CF
                if id == 'CF':
                    for equipo in range(1, conteo_instancias_CF+1):
                        filtro_CF = f"{i}.2.{equipo} CF"        
                        columnas_equipo_CF = df_trabajo.filter(like=filtro_CF).columns.to_list()
                        columnas_equipo_CF = ['#', 'user', f"{i}.1 Proyecto", 'Fecha visita ', 'Nombre del Cliente'] + columnas_equipo_CF
                        
                        #df trabajo se usa para la generación del informe
                        df_trabajo_equipo_CF = df_trabajo[columnas_equipo_CF]
                        dic_trabajo_CF = df_trabajo_equipo_CF.to_dict(orient='records')[0]

                        #Elmentos propios del equipo
                        modelo_CF = dic_trabajo_CF[f"{i}.2.{equipo} CF | Modelo"]
                        tipo_CF = dic_trabajo_CF[f"{i}.2.{equipo} CF | Activo a intervenir"]
                        serial_CF = dic_trabajo_CF[f'{i}.2.{equipo} CF | N° de serie']
                        operativo_CF = dic_trabajo_CF[f"{i}.2.{equipo} CF | ¿Equipo operativo tras trabajos?"]
                        obs_CF = dic_trabajo_CF[f'{i}.2.{equipo} CF | Observación']
                        alcance_CF = dic_trabajo_CF[f'{i}.2.{equipo} CF | Tipo de Ajuste']
                        
                        #Asegurando que el serial pase de float a int
                        for llave, valor in dic_trabajo_CF.items():
                                    if isinstance(valor,float):
                                        dic_trabajo_CF[llave] = int(valor)


                        pdf_stream_CF = informe_pdf_profesional(i, ot, tecnico, proyecto, fecha, cliente, tipo_CF, modelo_CF, serial_CF, id, alcance_CF, punto, obs_CF, obs_generales, lista_imagenes, equipo)
                        
                        nombre_archivo_CF = f"informe_OT-{ot}_{i}_{id}_{equipo}.pdf"

                        pdf_stream_CF.seek(0)

                        try:
                            contenido_pdf = pdf_stream_CF.read()
                            informe_codificado_CF = base64.b64encode(contenido_pdf).decode('utf-8')
                        except FileNotFoundError:
                            exit()

                        

                        #ACTUALIZACIÓN DE REQUEST
                        
                        #Buscamos las request que existan para el equipo en cuestión
                        try:
                            equipment_CF = odoo_client.search_read(
                                'maintenance.equipment',
                                [['serial_no', '=', serial_CF]],
                                limit=1
                            )
                        
                            if equipment_CF:
                                number_equipment_CF = equipment_CF[0]['id']

                                #Validación de ubicación
                                if equipment_CF[0]['x_studio_location']:
                                    location_CF = equipment_CF[0]['x_studio_location'][1]
                                else:
                                    location_CF = False
                                
                                #Equipo a reparar sin una instancia de instalación
                                puntos_odoo = odoo_client.search_read(
                                    'x_maintenance_location',
                                    [],
                                    fields=['id', 'x_name']
                                )

                                id_punto = None
                                for p in puntos_odoo:
                                    if p['x_name'] == f'[{proyecto}] {punto}':
                                        id_punto = p['id']
                                        break
                                

                                if not id_punto:
                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_CF, modelo_CF, serial_CF, id, 
                                            f'{punto} no se encuentra listado en Odoo y Connecteam')

                                    inbox(ot, operators[tecnico], fecha, False, tipo_CF, modelo_CF, serial_CF, id, odoo_client,
                                            f'{punto} no se encuentra listado en Odoo y Connecteam. Solicitar creación',
                                            'M',
                                            'Punto no existe en sistema',
                                            'Nuevo')
                                

                                if location_CF == False:

                                    try:
                                        star_location = odoo_client.message_post(
                                            'maintenance.equipment',
                                            number_equipment_CF,
                                            f"<p>Equipo sin evento de instalación We.</p><<p>Ubicación actual según OT-{ot}: {punto}</p>"
                                        )

                                        #trabajos sobre equipos que no estan con punto asignado
                                        inbox(ot, operators[tecnico], fecha, id_punto, tipo_CF, modelo_CF, serial_CF, id, odoo_client,
                                            f'Equipo sin evento de instalación We en el punto {punto}. Validar {nombre_archivo_CF}',
                                            'N',
                                            'Cambio de ubicación',
                                            'En proceso')
                                    
                                    except Exception as e:
                                        print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')
                    

                                elif location_CF != f'[{proyecto}] {punto}':
                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_CF, modelo_CF, serial_CF, id, 
                                                f'Equipo pasa de {location_CF} a [{proyecto}] {punto}). Validar {nombre_archivo_CF}')
                                    
                                    #Notificación por cambio de ubicación

                                    try:
                                        
                                        new_location_CF = odoo_client.message_post(
                                            'maintenance.equipment',
                                            number_equipment_CF,
                                            f"<p><b>La ubicación a cambiado.</b></p><p><b>Nueva ubicación según OT-{ot}:</b> {location_CF} => [{proyecto}] {punto}</p>"
                                        )

                                        inbox(ot, operators[tecnico], fecha, id_punto, tipo_CF, modelo_CF, serial_CF, id, odoo_client,
                                                f'Equipo pasa de {location_CF} a [{proyecto}] {punto}). Validar {nombre_archivo_CF}',
                                                'N',
                                                'Cambio de ubicación',
                                                'En proceso')
                                                

                                    except Exception as e:
                                        print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')  

                                try:
                                    domain_filter = [['equipment_id', '=', number_equipment_CF],
                                                    ['maintenance_type', '=', 'preventive'],
                                                    ['x_studio_tipo_de_trabajo', '=', 'Configuración']] #Productivo: x_studio_tipo_trabajo

                                    request_ids_CF = odoo_client.search(
                                        'maintenance.request',
                                        domain_filter,
                                    )
                                    
                                    #Iterando sobre las solicitudes que tiene el equipo
                                    if request_ids_CF:
                                    
                                        # interruptor_CF = True   
                                        interest_requests_CF = {} 
                                        for ids_CF in request_ids_CF:
                                            campos_de_interes_CF = ['schedule_date', 'stage_id', 'name', 'archive']
                                            try:
                                                request_data_CF = odoo_client.read(
                                                    'maintenance.request',
                                                    [ids_CF],
                                                    fields=campos_de_interes_CF
                                                )
                                                
                                                stage_id_CF = request_data_CF[0].get('stage_id') 
                                                schedule_date_CF = request_data_CF[0].get('schedule_date')
                                                name_CF = request_data_CF[0].get('name')
                                                archived_CF = request_data_CF[0].get('archive')

                                                # Solicitudes sin "Fecha programada"
                                                if schedule_date_CF == False or archived_CF == True:
                                                    continue
                                                # Solicitudes con fecha y finalizadas
                                                elif schedule_date_CF != False and stage_id_CF[0] == 5: #Finalizado
                                                    continue
                                                # Solicitudes con fecha y en desecho
                                                elif schedule_date_CF != False and stage_id_CF[0] == 4: #Desechar
                                                    continue
                                                else:
                                                    interest_requests_CF[ids_CF] = [schedule_date_CF, stage_id_CF, name_CF]
                                            
                                                    # interruptor_CF = False
                                                
                                            except Exception as e:
                                                print(e)

                                        # Buscamos la solicitud mas cercana a la fecha de realización del trabajo o aquella que se encuentra "en proceso"
                                        if interest_requests_CF:
                                            # Interruptor abierto por defecto para la no exitencia de un caso en proceso
                                            interruptor_CF = True
                                            id_CF = None

                                            for e in interest_requests_CF.keys():    
                                                # Interruptor cerrado si encuentra un caso en proceso
                                                if interest_requests_CF[e][1][0] == 3: #En proceso
                                                    interruptor_CF = False
                                                    id_CF = e
                                                    break
                                            
                                            # Si el interruptor sigue abierto, buscamos la solictud mas cercana a la fecha de realización del trabajo
                                            if interruptor_CF:
                                                id_CF = min(interest_requests_CF.keys(), key=lambda x: abs(pd.to_datetime(interest_requests_CF[x][0]) - pd.to_datetime(fecha)))
                                                
                                                #Archivamos las solicitudes anteriores a la escogida
                                                for x in interest_requests_CF.keys():
                                                    if interest_requests_CF[x][0] < interest_requests_CF[id_CF][0]:
                                                        try:
                                                            archive_CF = {
                                                                'archive': True,
                                                            }
                                                            update_stage_CF = odoo_client.write(
                                                                'maintenance.request',
                                                                [x], 
                                                                archive_CF
                                                            )
                                                        except Exception as e:
                                                            print(f"Error al archivar la solicitud {interest_requests_CF[x][2]}: {e}")
                                                        
                                            
                                            #Actualizamos el estado de la solicitud cuando el trabajo deja al equipo operativo
                                            if operativo_CF == "Sí":
                                                try:
                                                    #Atualizando su estado a Finalizado
                                                    update_CF = {
                                                        'stage_id': 5,
                                                        'x_studio_informe': informe_codificado_CF,
                                                    }

                                                    update_stage_CF = odoo_client.write(
                                                        'maintenance.request',
                                                        [id_CF], 
                                                        update_CF
                                                    )

                                                    close_date_CF = {
                                                            'close_date': fecha
                                                    }
                                                    
                                                    update_close_date_CF = odoo_client.write(
                                                        'maintenance.request',
                                                        [id_CF], 
                                                        close_date_CF
                                                    )

                                                    
                                                    if update_stage_CF:
                                                        detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_CF, modelo_CF, serial_CF, id, 
                                                                    f'Se registra con exito la configuración programado: {name_CF}')

                                                        inbox(ot, operators[tecnico], fecha, id_punto, tipo_CF, modelo_CF, serial_CF, id, odoo_client,
                                                            'Se registra con éxito el registro de configuración',
                                                            'A',
                                                            False,
                                                            'Resuelto')
                                                                
                                                        #Actualización de bitácora
                                                        try:
                                                            actividad_id_CF = odoo_client.search_read(
                                                                'mail.activity',
                                                                [['res_model', '=', 'maintenance.request'], ['res_id', '=', id_CF]],
                                                                limit=1
                                                            )

                                                            #Actualizando actividad
                                                            if actividad_id_CF:
                                                                try:
                                                                    actividad_number_CF = actividad_id_CF[0]['id']
                                                                    odoo_client.action_feedback(
                                                                        'mail.activity',
                                                                        [actividad_number_CF],
                                                                        f"Última ubicación: {punto}"
                                                                    )
                                                                    
                                                                except Exception as e:
                                                                    print(f"Error al actualizar estado de la actividad de mantenimiento: {e}")

                                                        except Exception as e:
                                                            print(f"Error al listar de la actividad de mantenimiento: {e}")
                                                
                                                        #  Buscamos el ID de la actividad existente para la OT
                                                                
                                                except Exception as e:
                                                    print(f"Error al actualizar estado de solicitud de mantenimiento CF: {e}")
                                                    traceback.print_exc()
                                                    continue
                                            
                                            #Actualizamos el estado de la solicitud cuando el trabajo no deja el equipo operativo
                                            elif operativo_CF == "No":
                                                try:
                                                    #Atualizando su estado a en proceso
                                                    update_CF = {
                                                        'stage_id': 3,
                                                    }

                                                    update_stage_CF = odoo_client.write(
                                                        'maintenance.request',
                                                        [id_CF], 
                                                        update_CF
                                                    )   

                                                    if update_stage_CF:
                                                        detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_CF, modelo_CF, serial_CF, id, 
                                                                    f'Se registra con exito la configuración programada: {name_CF}')

                                                        inbox(ot, operators[tecnico], fecha, id_punto, tipo_CF, modelo_CF, serial_CF, id, odoo_client,
                                                            'Se registra con éxito la configuración',
                                                            'A',
                                                            False,
                                                            'Resuelto')
                                                                                
                                                    
                                                        attachment_CF = odoo_client.create(
                                                            "ir.attachment",
                                                            {
                                                                "name": nombre_archivo_CF,
                                                                #"type": "binary",
                                                                "datas": informe_codificado_CF,
                                                                "res_model": 'maintenance.equipment',
                                                                "res_id": id_CF,
                                                                "mimetype": "application/pdf",
                                                            }
                                                        )

                                                        current_location_CF = odoo_client.message_post(
                                                            'maintenance.request',
                                                            id_CF,
                                                            f"<p><b>Ultima ubicación:</b> {punto}</p><p><b>Ejecutor:</b> {dic_trabajo_CF['user']}</p>",
                                                            attachment_ids=[attachment_CF]
                                                        )
                                                except Exception as e:
                                                    print(f"Error al actualizar estado de solicitud de configuración: {e}")
                                                    traceback.print_exc()
                                                    continue


                                        #Caso en que el equipo solo tiene solicitudes terminadas
                                        else:

                                            if operativo_CF == 'No':
                                                try:
                                                    fields_values_OT_CF = {
                                                        'name': f"Configuración | {tipo_CF} {modelo_CF}",
                                                        'equipment_id': number_equipment_CF, #Aquí debemos usar el ID númerico de la sonda
                                                        'stage_id': '3', # 3 En proceso 
                                                        'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                        # 'x_studio_etiqueta_1': id_mantencion[id],
                                                        'schedule_date': f"{fecha}",
                                                        'description': f'<p><b>{alcance_CF}</b></p><p>{obs_CF}</p>'
                                                    }

                                                    created_request_CF = odoo_client.create(
                                                        'maintenance.request',
                                                        fields_values_OT_CF
                                                    )
                                                    
                                                    #Resgistro en resumen
                                                    detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_CF, modelo_CF, serial_CF, id,
                                                                f'Se crea con éxito el registro de configuración {created_request_CF}')

                                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_CF, modelo_CF, serial_CF, id, odoo_client,
                                                            'Se crea con éxito el registro de configuración',
                                                            'A',
                                                            False,
                                                            'Resuelto')
                                            
                                                    
                                                    attachment_CF = odoo_client.create(
                                                        "ir.attachment",
                                                        {
                                                            "name": nombre_archivo_CF,
                                                            #"type": "binary",
                                                            "datas": informe_codificado_CF,
                                                            "res_model": 'maintenance.equipment',
                                                            "res_id": created_request_CF,
                                                            "mimetype": "application/pdf",
                                                        }
                                                    )

                                                    current_location_CF = odoo_client.message_post(
                                                        'maintenance.request',
                                                        created_request_CF,
                                                        f"<p><b>Ultima ubicación:</b> {punto}</p><p><b>Ejecutor:</b> {tecnico}</p>",
                                                        attachment_ids=[attachment_CF]
                                                    )

                                                    

                                                except Exception as e:
                                                    print(f"Error al crear request CF para la OT-{dic_trabajo_CF['#']} en Odoo: {type(e)}")
                                                    print(traceback.format_exc())
                                                    continue

                                            # Se realiza el trabajo y queda operativo el dispositivo
                                            elif operativo_CF == 'Sí':
                                                try:
                                                    fields_values_OT_CF = {
                                                        'name': f"Configuración | {tipo_CF} {modelo_CF}",
                                                        'equipment_id': number_equipment_CF, #Aquí debemos usar el ID númerico de la sonda
                                                        'stage_id': '5', # 5 Finalizado
                                                        'description': f'<p><b>{alcance_CF}</b></p><p>{obs_CF}</p>',
                                                        'schedule_date': f"{fecha}",
                                                        'x_studio_informe': informe_codificado_CF,
                                                        'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                        # 'x_studio_etiqueta_1': id_mantencion[id],

                                                    }
                                                    created_request_CF = odoo_client.create(
                                                        'maintenance.request',
                                                        fields_values_OT_CF
                                                    )

                                                    #Hacemos la escritura para que se actualice la fecha de cierre
                                                    update_stage_CF = {
                                                        'stage_id': 5,
                                                    }

                                                    update_stage_CF = odoo_client.write(
                                                        'maintenance.request',
                                                        [created_request_CF], 
                                                        update_stage_CF
                                                    )

                                                    update_close_date_CF = {
                                                        'close_date': fecha,
                                                        'x_studio_tcnico': operators[tecnico]
                                                    }

                                                    update_close_date_CF = odoo_client.write(
                                                        'maintenance.request',
                                                        [created_request_CF], 
                                                        update_close_date_CF
                                                    )

                                                    #Resgistro en resumen
                                                    detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_CF, modelo_CF, serial_CF, id,
                                                                f'Se crea con éxito el registro de configuración {created_request_CF}')

                                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_CF, modelo_CF, serial_CF, id, odoo_client,
                                                        'Se crea con éxito el registro de configuración',
                                                        'A',
                                                        False,
                                                        'Resuelto')

                                                    
                                                    
                                                    #Actualización de la actividad por defecto 'Maintenance Request'
                                                    #Buscando el ID de la OT creada
                                                    id_CF = odoo_client.search(
                                                        'maintenance.request',
                                                        [['id', '=', created_request_CF]],
                                                        limit=1
                                                    )
                                                    
                                                    try:
                                                        #Buscamos el ID de la actividad existente para la OT_number
                                                        actividad_id_CF = odoo_client.search_read(
                                                            'mail.activity',
                                                            [['res_model', '=', 'maintenance.request'], ['res_id', '=', created_request_CF]],
                                                            limit=1
                                                        )

                                                        #Actualizando actividad
                                                        try:
                                                            actividad_number_CF = actividad_id_CF[0]['id']
                                                            odoo_client.action_feedback(
                                                                'mail.activity',
                                                                [actividad_number_CF],
                                                                f"Última ubicación: {punto}"
                                                            )

                                                        except Exception as e:
                                                            print(f"Error al actualizar la actividad de mantenimiento asociada: {e}")
                                                            continue        
                                                        
                                                    except Exception as e:
                                                        print(f"Error al buscar la actividad de manteniminto asociada: {e}") 
                                                        continue   

                                            
                                                except Exception as e:
                                                    print(f"Error al crear request CF para la OT-{dic_trabajo_CF['#']} en Odoo: {type(e)}")
                                                    print(traceback.format_exc())
                                                    continue
                                            



                                    #Caso en que el equipo no tiene solicitudes de ninguna naturaleza 
                                            
                                    else:

                                        if operativo_CF == 'No':
                                            try:
                                                fields_values_OT_CF = {
                                                    'name': f"Configuración | {tipo_CF} {modelo_CF}",
                                                    'equipment_id': number_equipment_CF, #Aquí debemos usar el ID númerico de la sonda
                                                    'stage_id': '3', # 3 En proceso 
                                                    'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                    # 'x_studio_etiqueta_1': id_mantencion[id],
                                                    'schedule_date': f"{fecha}",
                                                    'description': f'<p><b>{alcance_CF}</b></p><p>{obs_CF}</p>'
                                                }

                                                created_request_CF = odoo_client.create(
                                                    'maintenance.request',
                                                    fields_values_OT_CF
                                                )
                                                
                                                #Resgistro en resumen
                                                detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_CF, modelo_CF, serial_CF, id,
                                                            f'Se crea con éxito el registro de configuración {created_request_CF}')

                                                inbox(ot, operators[tecnico], fecha, id_punto, tipo_CF, modelo_CF, serial_CF, id, odoo_client,
                                                        'Se crea con éxito el registro de configuración',
                                                        'A',
                                                        False,
                                                        'Resuelto')
                                        
                                                
                                                attachment_CF = odoo_client.create(
                                                    "ir.attachment",
                                                    {
                                                        "name": nombre_archivo_CF,
                                                        #"type": "binary",
                                                        "datas": informe_codificado_CF,
                                                        "res_model": 'maintenance.equipment',
                                                        "res_id": created_request_CF,
                                                        "mimetype": "application/pdf",
                                                    }
                                                )

                                                current_location_CF = odoo_client.message_post(
                                                    'maintenance.request',
                                                    created_request_CF,
                                                    f"<p><b>Ultima ubicación:</b> {punto}</p><p><b>Ejecutor:</b> {tecnico}</p>",
                                                    attachment_ids=[attachment_CF]
                                                )

                                                

                                            except Exception as e:
                                                print(f"Error al crear request CF para la OT-{dic_trabajo_CF['#']} en Odoo: {type(e)}")
                                                print(traceback.format_exc())
                                                continue

                                        # Se realiza el trabajo y queda operativo el dispositivo
                                        elif operativo_CF == 'Sí':
                                            try:
                                                fields_values_OT_CF = {
                                                    'name': f"Configuración | {tipo_CF} {modelo_CF}",
                                                    'equipment_id': number_equipment_CF, #Aquí debemos usar el ID númerico de la sonda
                                                    'stage_id': '5', # 5 Finalizado
                                                    'description': f'<p><b>{alcance_CF}</b></p><p>{obs_CF}</p>',
                                                    'schedule_date': f"{fecha}",
                                                    'x_studio_informe': informe_codificado_CF,
                                                    'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                    # 'x_studio_etiqueta_1': id_mantencion[id],

                                                }
                                                created_request_CF = odoo_client.create(
                                                    'maintenance.request',
                                                    fields_values_OT_CF
                                                )

                                                #Hacemos la escritura para que se actualice la fecha de cierre
                                                update_stage_CF = {
                                                    'stage_id': 5,
                                                }

                                                update_stage_CF = odoo_client.write(
                                                    'maintenance.request',
                                                    [created_request_CF], 
                                                    update_stage_CF
                                                )

                                                update_close_date_CF = {
                                                    'close_date': fecha,
                                                    'x_studio_tcnico': operators[tecnico]
                                                }

                                                update_close_date_CF = odoo_client.write(
                                                    'maintenance.request',
                                                    [created_request_CF], 
                                                    update_close_date_CF
                                                )

                                                #Resgistro en resumen
                                                detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_CF, modelo_CF, serial_CF, id,
                                                            f'Se crea con éxito el registro de configuración {created_request_CF}')

                                                inbox(ot, operators[tecnico], fecha, id_punto, tipo_CF, modelo_CF, serial_CF, id, odoo_client,
                                                    'Se crea con éxito el registro de configuración',
                                                    'A',
                                                    False,
                                                    'Resuelto')

                                                
                                                
                                                #Actualización de la actividad por defecto 'Maintenance Request'
                                                #Buscando el ID de la OT creada
                                                id_CF = odoo_client.search(
                                                    'maintenance.request',
                                                    [['id', '=', created_request_CF]],
                                                    limit=1
                                                )
                                                
                                                try:
                                                    #Buscamos el ID de la actividad existente para la OT_number
                                                    actividad_id_CF = odoo_client.search_read(
                                                        'mail.activity',
                                                        [['res_model', '=', 'maintenance.request'], ['res_id', '=', created_request_CF]],
                                                        limit=1
                                                    )

                                                    #Actualizando actividad
                                                    try:
                                                        actividad_number_CF = actividad_id_CF[0]['id']
                                                        odoo_client.action_feedback(
                                                            'mail.activity',
                                                            [actividad_number_CF],
                                                            f"Última ubicación: {punto}"
                                                        )

                                                    except Exception as e:
                                                        print(f"Error al actualizar la actividad de configuración asociada: {e}")
                                                        continue        
                                                    
                                                except Exception as e:
                                                    print(f"Error al buscar la actividad de manteniminto asociada: {e}") 
                                                    continue   

                                        
                                            except Exception as e:
                                                print(f"Error al crear request CF para la OT-{dic_trabajo_CF['#']} en Odoo: {type(e)}")
                                                print(traceback.format_exc())
                                                continue

        
                                except Exception as e: 
                                    print(f"Error al obtener información de la solicitudes de configuración: {e}")
                                    continue 

                            else:   

                                try:
                                    sharepoint_client.upload_file(f'{SHAREPOINT_UPLOAD_BASE_URL}/{nombre_archivo_CF}:/content', pdf_stream_CF, "application/pdf" )
                                except Exception as e:
                                    print(f"Error al subir el informe al Sharepoint: {e}")

                                detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_CF, modelo_CF, serial_CF, id, 
                                            f'N° de serie no encontrado en Odoo. Revisar OT | {nombre_archivo_CF}')
                                

                                punto_odoo = odoo_client.search_read(
                                    'x_maintenance_location',
                                    [['x_name', '=', f'[{proyecto}] {punto}']],
                                    limit=1
                                )

                                id_punto = punto_odoo[0]['id']

                                if not id_punto:
                                    id_punto = False
                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_CF, modelo_CF, serial_CF, id, 
                                            f'{punto} no se encuentra listado en Odoo y Connecteam')

                                    inbox(ot, operators[tecnico], fecha, False, tipo_CF, modelo_CF, serial_CF, id, odoo_client,
                                            f'{punto} no se encuentra listado en Odoo y Connecteam. Solicitar creación',
                                            'M',
                                            'Punto no existe en sistema',
                                            'Nuevo')




                                domain = [
                                    ('location_usage', '=', 'transit'),
                                    ('location_dest_usage', '=', 'customer'),
                                    ('lot_id.name', '=', serial_CF),
                                    # ('reference', '=', 'WH/OUT/00189'),
                                    ('state', 'not in', ['done', 'cancel'])  # Filtra para que NO sea 'done' ni 'cancel'
                                ]

                                search_read = odoo_client.search_read(
                                    'stock.move.line',
                                    domain,
                                    limit=1
                                )


                                if search_read:
                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_CF, modelo_CF, serial_CF, id, odoo_client,
                                            f'N° de serie no encontrado en Odoo. Revisar OT | {nombre_archivo_CF}',
                                            'M',
                                            'Creación en espera',
                                            'Nuevo')
                                else:
                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_CF, modelo_CF, serial_CF, id, odoo_client,
                                            f'N° de serie no encontrado en Odoo. Revisar OT | {nombre_archivo_CF}',
                                            'M',
                                            'S/N no encontrado',
                                            'Nuevo')

                                continue
                    
                        except Exception as e:
                                    print(f"Error al buscar equipo en base de Odoo CF: {e}")
                    



                #Tratamiento para CI
                if id == 'CI':
                    for equipo in range(1, conteo_instancias_CI+1):
                        filtro_CI = f"{i}.2.{equipo} CI"        
                        columnas_equipo_CI = df_trabajo.filter(like=filtro_CI).columns.to_list()
                        columnas_equipo_CI = ['#', 'user', f"{i}.1 Proyecto", 'Fecha visita ', 'Nombre del Cliente'] + columnas_equipo_CI
                        
                        #df trabajo se usa para la generación del informe
                        df_trabajo_equipo_CI = df_trabajo[columnas_equipo_CI]
                        dic_trabajo_CI = df_trabajo_equipo_CI.to_dict(orient='records')[0]

                        #Elmentos propios del equipo
                        etapa_CI = dic_trabajo_CI[f"{i}.2.{equipo} CI | Etapa"]
                        modelo_CI = dic_trabajo_CI[f"{i}.2.{equipo} CI | Modelo"]
                        serial_CI = dic_trabajo_CI[f'{i}.2.{equipo} CI | N° de serie']
                        obs_CI = dic_trabajo_CI[f'{i}.2.{equipo} CI | Observación']
                        
                        
                        #Asegurando que el serial pase de float a int
                        for llave, valor in dic_trabajo_CI.items():
                                    if isinstance(valor,float):
                                        dic_trabajo_CI[llave] = int(valor)

                        
                        #Buscamos las request que existan para el equipo en cuestión
                        try:
                            equipment_CI = odoo_client.search_read(
                                'maintenance.equipment',
                                [['serial_no', '=', serial_CI]],
                                limit=1
                            )
                        
                            if equipment_CI:
                                number_equipment_CI = equipment_CI[0]['id']

                                #Validación de ubicación
                                if equipment_CI[0]['x_studio_location']:
                                    location_CI = equipment_CI[0]['x_studio_location'][1]
                                else:
                                    location_CI = False
                                
                                #Equipo a reparar sin una instancia de instalación
                                puntos_odoo = odoo_client.search_read(
                                    'x_maintenance_location',
                                    [],
                                    fields=['id', 'x_name']
                                )

                                id_punto = None
                                for p in puntos_odoo:
                                    if p['x_name'] == f'[{proyecto}] {punto}':
                                        id_punto = p['id']
                                        break
                                

                                if not id_punto:
                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, 
                                            f'{punto} no se encuentra listado en Odoo y Connecteam')

                                    inbox(ot, operators[tecnico], fecha, False, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, odoo_client,
                                            f'{punto} no se encuentra listado en Odoo y Connecteam. Solicitar creación',
                                            'M',
                                            'Punto no existe en sistema',
                                            'Nuevo')
                                

                                if location_CI == False:

                                    try:
                                        star_location = odoo_client.message_post(
                                            'maintenance.equipment',
                                            number_equipment_CI,
                                            f"<p>Equipo sin evento de instalación We.</p><<p>Ubicación actual según OT-{ot}: {punto}</p>"
                                        )

                                        #trabajos sobre equipos que no estan con punto asignado
                                        inbox(ot, operators[tecnico], fecha, id_punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, odoo_client,
                                            f'Equipo sin evento de instalación We en el punto {punto}. Validar {nombre_archivo_CI}',
                                            'N',
                                            'Cambio de ubicación',
                                            'En proceso')
                                    
                                    except Exception as e:
                                        print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')
                    

                                elif location_CI != f'[{proyecto}] {punto}':
                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, 
                                                f'Equipo pasa de {location_CI} a {punto}). Validar {nombre_archivo_CI}')
                                    
                                    #Notificación por cambio de ubicación

                                    try:
                                        
                                        new_location_CI = odoo_client.message_post(
                                            'maintenance.equipment',
                                            number_equipment_CI,
                                            f"<p><b>La ubicación a cambiado.</b></p><p><b>Nueva ubicación según OT-{ot}:</b> {location_CI} => [{proyecto}] {punto}</p>"
                                        )

                                        inbox(ot, operators[tecnico], fecha, id_punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, odoo_client,
                                                f'Equipo pasa de {location_CI} a {punto}). Validar {nombre_archivo_CI}',
                                                'N',
                                                'Cambio de ubicación',
                                                'En proceso')
                                                

                                    except Exception as e:
                                        print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')  

                                try:
                                    domain_filter = [['equipment_id', '=', number_equipment_CI],
                                                    ['maintenance_type', '=', 'preventive'],
                                                    ['x_studio_tipo_de_trabajo', '=', 'Calibración']] #Productivo: x_studio_tipo_trabajo

                                    request_ids_CI = odoo_client.search(
                                        'maintenance.request',
                                        domain_filter,
                                    )
                                    
                                    #Iterando sobre las solicitudes que tiene el equipo
                                    if request_ids_CI:
                                    
                                        interruptor_MP = True   
                                        interest_requests_CI = {} 
                                        for ids_CI in request_ids_CI:
                                            campos_de_interes_CI = ['schedule_date', 'stage_id', 'name', 'archive']
                                            try:
                                                request_data_CI = odoo_client.read(
                                                    'maintenance.request',
                                                    [ids_CI],
                                                    fields=campos_de_interes_CI
                                                )
                                                
                                                stage_id_CI = request_data_CI[0].get('stage_id') 
                                                schedule_date_CI = request_data_CI[0].get('schedule_date')
                                                name_CI = request_data_CI[0].get('name')
                                                archived_CI = request_data_CI[0].get('archive')

                                                #Solicitudes sin "Fecha programada"
                                                if schedule_date_CI == False or archived_CI == True:
                                                    continue
                                                #Solicitudes con fecha y finalizadas
                                                elif schedule_date_CI != False and stage_id_CI[0] == 5: #Finalizado
                                                    continue
                                                #Solicitudes con fecha y en desecho
                                                elif schedule_date_CI != False and stage_id_CI[0] == 4: #Desechar
                                                    continue
                                                else:
                                                    interest_requests_CI[ids_CI] = [schedule_date_CI, stage_id_CI, name_CI]
                                            
                                                 
                                            except Exception as e:
                                                print(e)

                                        #Buscamos la solicitud mas cercana a la fecha de realización del trabajo o aquella que se encuentra "en proceso"
                                        if interest_requests_CI:
                                            #Interruptor abierto por defecto para la no exitencia de un caso en proceso
                                            interruptor_CI = True
                                            id_CI = None

                                            #Tratamiento para 
                                            for e in interest_requests_CI.keys():
                                                
                                             #   Interruptor cerrado si encuentra un caso en proceso
                                                if interest_requests_CI[e][1][0] == 3: #En proceso
                                                    interruptor_CI = False
                                                    id_CI = e
                                                    break
                                            
                                            #Si el interruptor sigue abierto, buscamos la solictud mas cercana a la fecha de realización del trabajo
                                            if interruptor_CI:
                                                id_CI = min(interest_requests_CI.keys(), key=lambda x: abs(pd.to_datetime(interest_requests_CI[x][0]) - pd.to_datetime(fecha)))
                                                
                                             #   Archivamos las solicitudes anteriores a la escogida
                                                for x in interest_requests_CI.keys():
                                                    if interest_requests_CI[x][0] < interest_requests_CI[id_CI][0]:
                                                        try:
                                                            archive_CI = {
                                                                'archive': True,
                                                            }
                                                            update_stage_CI = odoo_client.write(
                                                                'maintenance.request',
                                                                [x], 
                                                                archive_CI
                                                            )
                                                        except Exception as e:
                                                            print(f"Error al archivar la solicitud {interest_requests_CI[x][2]}: {e}")
                                            

                                            if etapa_CI == "Extracción":
                                                
                                                if interest_requests_CI[id_CI][1][0] == 3:

                                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, 
                                                                f'Registro de extracción cuando la sonda no se enceuntra en el punto')
                                                    
                                                    inbox(ot, operators[tecnico], fecha, id_punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, odoo_client,
                                                                'Registro de extraccción cuando la sonda no se encuentra en el punto',
                                                                'M',
                                                                False,
                                                                'Nuevo')
                                                    
                                                    continue

                                                try:
                                                   # Atualizando su estado a Finalizado
                                                    update_CI = {
                                                        'stage_id': 3,
                                                 
                                                    }

                                                    update_stage_CI = odoo_client.write(
                                                        'maintenance.request',
                                                        [id_CI], 
                                                        update_CI
                                                    )

                                                    tec_CI = {
                                                    'x_studio_tcnico': operators[tecnico]
                                                    }

                                                    update_close_date_CI = odoo_client.write(
                                                        'maintenance.request',
                                                        [id_CI], 
                                                        tec_CI
                                                    )


                                                    if update_stage_CI:
                                                        detalle_op(exito, ot, tecnico, fecha, proyecto, punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, 
                                                                    f'Se registra con exito la instancia de extracción para la calibración: {name_CI}')
                                                        
                                                        inbox(ot, operators[tecnico], fecha, id_punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, odoo_client,
                                                                    'Se regista con exito la instancia de extracción',
                                                                    'A',
                                                                    False,
                                                                    'Resuelto')
                                                            
                                                        #Actualización de bitácora
                                                        star_location = odoo_client.message_post(
                                                            'maintenance.request',
                                                            id_CI,
                                                            f"Punto de extracción: [{proyecto}] {punto}"
                                                        )
                                                      
                                                      #   Buscamos el ID de la actividad existente para la OT
                                                                
                                                except Exception as e:
                                                    print(f"Error al actualizar estado de solicitud de mantenimiento MP: {e}")
                                                    traceback.print_exc()
                                                    continue
                                            
                                            else:
                                                
                                                if interest_requests_CI[id_CI][1][0] != 3:

                                                    detalle_op(exito, ot, tecnico, fecha, proyecto, punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, 
                                                                f'Registro de re-instalación cuando no se ha extraido la sonda')
                                                    
                                                    inbox(ot, operators[tecnico], fecha, id_punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, odoo_client,
                                                                'Registro de re-instalación cuando la sonda no ha sido extraida del punto',
                                                                'M',
                                                                False,
                                                                'Nuevo')
                                                    
                                                    continue


                                                try:
                                                    #Atualizando su estado a Finalizado
                                                    update_CI = {
                                                        'stage_id': 5,
                                                  
                                                    }

                                                    update_stage_CI = odoo_client.write(
                                                        'maintenance.request',
                                                        [id_CI], 
                                                        update_CI
                                                    )


                                                    close_date_CI = {
                                                        'close_date': fecha,
                                                    'x_studio_tcnico': operators[tecnico]
                                                    }

                                                    update_close_date_CI = odoo_client.write(
                                                        'maintenance.request',
                                                        [id_CI], 
                                                        close_date_MP
                                                    )

                        
                                                    if update_stage_CI:
                                                        detalle_op(exito, ot, tecnico, fecha, proyecto, punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, 
                                                                    f'Se registra con exito la instancia de re-instalación para la calibración: {name_CI}')
                                                        
                                                        inbox(ot, operators[tecnico], fecha, id_punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, odoo_client,
                                                                    'Se regista con exito la instancia de re-instalación',
                                                                    'A',
                                                                    False,
                                                                    'Resuelto')
                                                            
                                                        #Actualización de bitácora
                                                        try:
                                                            actividad_id_CI = odoo_client.search_read(
                                                                'mail.activity',
                                                                [['res_model', '=', 'maintenance.request'], ['res_id', '=', id_CI]],
                                                                limit=1
                                                            )

                                                            #Actualizando actividad
                                                            if actividad_id_CI:
                                                                try:
                                                                    actividad_number_CI = actividad_id_CI[0]['id']
                                                                    odoo_client.action_feedback(
                                                                        'mail.activity',
                                                                        [actividad_number_CI],
                                                                        f"<b>Punto de re-instalación:</b> [{proyecto}] {punto}"
                                                                    )
                                                                    
                                                                except Exception as e:
                                                                    print(f"Error al actualizar estado de la actividad de mantenimiento: {e}")

                                                        except Exception as e:
                                                            print(f"Error al listar de la actividad de mantenimiento: {e}")
                                                
                                                        # Buscamos el ID de la actividad existente para la OT
                                                                
                                                except Exception as e:
                                                    print(f"Error al actualizar estado de solicitud de mantenimiento MP: {e}")
                                                    traceback.print_exc()
                                                    continue
                                        
                                        #Caso en que el equipo solo tiene solicitudes terminadas
                                        else:
                                        
                                            if etapa_CI == "Extracción":
                                                try:
                                                    fields_values_OT_CI = {
                                                        'name': f"Calibración | Sonda multiparamétrica {modelo_CI}",
                                                        'equipment_id': number_equipment_CI, #Aquí debemos usar el ID númerico de la sonda
                                                        'stage_id': '3', # 5 Finalizado
                                                        'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                        # 'x_studio_etiqueta_1': id_mantencion[id],
                                                        'description': obs_CI,
                                                        'schedule_date': fecha,
                                                        'x_studio_tcnico': operators[tecnico]

                                                    }
                                                    created_request_CI = odoo_client.create(
                                                        'maintenance.request',
                                                        fields_values_OT_CI
                                                    )
                                                    
                                                    detalle_op(exito, ot, tecnico, fecha, proyecto, punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id,
                                                                f'Se crea con éxito el registro de calibración {created_request_CI}')
                                                    
                                                    inbox(ot, operators[tecnico], fecha, id_punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, odoo_client,
                                                                'Se crea con éxito el registro de extracción de sonda',
                                                                'A',
                                                                False,
                                                                'Resuelto')

                                                except Exception as e:
                                                    print(f'Creación de instancia {e}')

                                            elif etapa_CI == 'Re-instalación':
                                                try:
                                                    fields_values_OT_CI = {
                                                        'name': f"Calibración | Sonda multiparamétrica {modelo_CI}",
                                                        'equipment_id': number_equipment_CI, #Aquí debemos usar el ID númerico de la sonda
                                                        'stage_id': '5', # 5 Finalizado
                                                        'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                        # 'x_studio_etiqueta_1': id_mantencion[id],
                                                        'description': obs_CI,
                                                        'schedule_date': fecha,
                                                    }

                                                    created_request_CI = odoo_client.create(
                                                        'maintenance.request',
                                                        fields_values_OT_CI
                                                    )

                                                    #Hacemos la escritura para que se actualice la fecha de cierre
                                                    update_stage_CI = {
                                                        'stage_id': 5,
                                                    }

                                                    update_stage_CI = odoo_client.write(
                                                        'maintenance.request',
                                                        [created_request_CI], 
                                                        update_stage_CI
                                                    )

                                                    update_close_date_CI = {
                                                        'close_date': fecha,
                                                        'x_studio_tcnico': operators[tecnico]
                                                    }

                                                    update_close_date_CI = odoo_client.write(
                                                        'maintenance.request',
                                                        [created_request_CI], 
                                                        update_close_date_CI
                                                    )

                                                    #Resgistro en resumen
                                                    
                                                    detalle_op(exito, ot, tecnico, fecha, proyecto, punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id,
                                                                f'Se crea con éxito el registro de calibración {created_request_CI}')
                                                    
                                                    inbox(ot, operators[tecnico], fecha, id_punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, odoo_client,
                                                                'Se crea con éxito el registro de reinstalación de sonda',
                                                                'A',
                                                                False,
                                                                'Resuelto')

                                                    try:
                                                        actividad_id_CI = odoo_client.search_read(
                                                            'mail.activity',
                                                            [['res_model', '=', 'maintenance.request'], ['res_id', '=', created_request_CI]],
                                                            limit=1
                                                        )

                                                       # Actualizando actividad
                                                        if actividad_id_CI:
                                                            try:
                                                                actividad_number_CI = actividad_id_CI[0]['id']
                                                                odoo_client.action_feedback(
                                                                    'mail.activity',
                                                                    [actividad_number_CI],
                                                                    f"<b>Punto de re-instalación:</b> [{proyecto}] {punto}"
                                                                )
                                                                
                                                            except Exception as e:
                                                                print(f"Error al actualizar estado de la actividad de mantenimiento: {e}")

                                                    except Exception as e:
                                                        print(f"Error al listar de la actividad de mantenimiento: {e}")

                                                except Exception as e:
                                                    print(f'Error al crear intancia {e}')      
                                            


                                    #Caso cuando el equipo no tiene solicitudes programadas ni realizadas        
                                    else:
                                        
                                        if etapa_CI == "Extracción":
                                            try:
                                                fields_values_OT_CI = {
                                                    'name': f"Calibración | Sonda multiparamétrica {modelo_CI}",
                                                    'equipment_id': number_equipment_CI, #Aquí debemos usar el ID númerico de la sonda
                                                    'stage_id': '3', # 5 Finalizado
                                                    'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                    # 'x_studio_etiqueta_1': id_mantencion[id],
                                                    'description': obs_CI,
                                                    'schedule_date': fecha,
                                                    'x_studio_tcnico': operators[tecnico]
                                                }

                                                created_request_CI = odoo_client.create(
                                                        'maintenance.request',
                                                        fields_values_OT_CI
                                                    )
                                                
                                                detalle_op(exito, ot, tecnico, fecha, proyecto, punto, 'Sonda multiparamétrica', modelo_MP, serial_MP, id,
                                                            f'Se crea con éxito el registro de calibración {created_request_MP}')
                                                
                                                inbox(ot, operators[tecnico], fecha, id_punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, odoo_client,
                                                            'Se crea con éxito el registro de extracción de sonda',
                                                            'A',
                                                            False,
                                                            'Resuelto')

                                            except Exception as e:
                                                print('Creación de instancia')

                                        elif etapa_CI == 'Re-instalación':
                                            try:
                                                fields_values_OT_CI = {
                                                    'name': f"Calibración | Sonda multiparamétrica {modelo_CI}",
                                                    'equipment_id': number_equipment_CI, #Aquí debemos usar el ID númerico de la sonda
                                                    'stage_id': '5', # 5 Finalizado
                                                    'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                    # 'x_studio_etiqueta_1': id_mantencion[id],
                                                    'description': obs_CI,
                                                    'schedule_date': fecha,
                                                }

                                                created_request_CI = odoo_client.create(
                                                    'maintenance.request',
                                                    fields_values_OT_CI
                                                )

                                                #Hacemos la escritura para que se actualice la fecha de cierre
                                                update_stage_CI = {
                                                    'stage_id': 5,
                                                }

                                                update_stage_CI = odoo_client.write(
                                                    'maintenance.request',
                                                    [created_request_CI], 
                                                    update_stage_CI
                                                )

                                                update_close_date_CI = {
                                                    'close_date': fecha,
                                                    'x_studio_tcnico': operators[tecnico]
                                                }

                                                update_close_date_CI = odoo_client.write(
                                                    'maintenance.request',
                                                    [created_request_CI], 
                                                    update_close_date_CI
                                                )

                                                #Resgistro en resumen
                    
                                                detalle_op(exito, ot, tecnico, fecha, proyecto, punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id,
                                                            f'Se crea con éxito el registro de calibración {created_request_CI}')
                                                
                                                inbox(ot, operators[tecnico], fecha, id_punto, 'Sonda multiparamétrica', modelo_CI, serial_CI, id, odoo_client,
                                                            'Se crea con éxito el registro de reinstalación de sonda',
                                                            'A',
                                                            False,
                                                            'Resuelto')

                                                #Actualización de la actividad por defecto 'Maintenance Request'

                                                try:
                                                    #Buscamos el ID de la actividad existente para la OT_number
                                                    actividad_id_CI = odoo_client.search_read(
                                                        'mail.activity',
                                                        [['res_model', '=', 'maintenance.request'], ['res_id', '=', created_request_CI]],
                                                        limit=1
                                                    )

                                                    #Actualizando actividad
                                                    try:
                                                        actividad_number_CI = actividad_id_CI[0]['id']
                                                        odoo_client.action_feedback(
                                                            'mail.activity',
                                                            [actividad_number_CI],
                                                            f"Se ha completado desde API | Última ubicación: {punto}"
                                                        )

                                                    except Exception as e:
                                                        print(f"Error al actualizar la actividad de mantenimiento asociada: {e}")
                                                        continue        
                                                    
                                                except Exception as e:
                                                    print(f"Error al buscar la actividad de manteniminto asociada: {e}") 
                                                    continue 

                                            except Exception as e:
                                                print(f'Error al crear instancia: {e}')      


                                except Exception as e:
                                    print(f"Error al obtener información de la solicitudes de mantenimiento: {e}")
                                    continue 
                            else:

                          
                                detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_CI, modelo_CI, serial_CI, id, 
                                            f'N° de serie no encontrado en Odoo. Revisar OT | {ot}')
                                

                                punto_odoo = odoo_client.search_read(
                                    'x_maintenance_location',
                                    [['x_name', '=', f'[{proyecto}] {punto}']],
                                    limit=1
                                )
                                
                               # Id del punto dentro de Odoo
                                id_punto = punto_odoo[0]['id']

                                if not id_punto:
                                    id_punto = False
                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_CI, modelo_CI, serial_CI, id, 
                                            f'{punto} no se encuentra listado en Odoo y Connecteam')

                                    inbox(ot, operators[tecnico], fecha, False, tipo_CI, modelo_CI, serial_CI, id, odoo_client,
                                            f'{punto} no se encuentra listado en Odoo y Connecteam. Solicitar creación',
                                            'M',
                                            'Punto no existe en sistema',
                                            'Nuevo')


                                domain = [
                                    ('location_usage', '=', 'transit'),
                                    ('location_dest_usage', '=', 'customer'),
                                    ('lot_id.name', '=', serial_CI),
                                    # ('reference', '=', 'WH/OUT/00189'),
                                    ('state', 'not in', ['done', 'cancel'])  # Filtra para que NO sea 'done' ni 'cancel'
                                ]

                                search_read = odoo_client.search_read(
                                    'stock.move.line',
                                    domain,
                                    limit=1
                                )


                                if search_read:
                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_CI, modelo_CI, serial_CI, id, odoo_client,
                                            f'N° de serie no encontrado en Odoo. Revisar OT',
                                            'M',
                                            'Creación en espera',
                                            'Nuevo')
                                else:
                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_CI, modelo_CI, serial_CI, id, odoo_client,
                                            f'N° de serie no encontrado en Odoo. Revisar OT',
                                            'M',
                                            'S/N no encontrado',
                                            'Nuevo')
                        
                        except Exception as e:
                            print(f"Error al buscar equipo en base de Odoo MP: {e}")                
                    
                
                elif id == "I":
                    #Iteramos sobre los tipos de mantenimientos

                    for t in I_type:

                        #Itereramos sobre la cantidad de intalaciones del tipo t que se realizaron

                        for equipo in range(1, conteo_I[t]+1):

                            filtro_I = f"{i}.2.{equipo} I ({t})"        
                            columnas_equipo_I = df_trabajo.filter(like=filtro_I).columns.to_list()
                            columnas_equipo_I = ['#', 'user', f"{i}.1 Proyecto", 'Fecha visita ', 'Nombre del Cliente'] + columnas_equipo_I
                            
                         #   df trabajo se usa para la generación del informe
                            df_trabajo_equipo_I = df_trabajo[columnas_equipo_I]
                            dic_trabajo_I = df_trabajo_equipo_I.to_dict(orient='records')[0]

                          #  Elmentos propios del equipo
                            modelo_I = dic_trabajo_I[f"{i}.2.{equipo} I ({t}) | Modelo"]
                            tipo_I = dic_trabajo_I[f"{i}.2.{equipo} I ({t}) | Tipo de {I_translate[t]}"]
                            serial_I = dic_trabajo_I[f'{i}.2.{equipo} I ({t}) | N° de serie']
                            operativo_I = dic_trabajo_I[f"{i}.2.{equipo} I ({t}) | ¿Equipo operativo tras trabajos?"]
                            obs_I = dic_trabajo_I[f'{i}.2.{equipo} I ({t}) | Observación']
                            alcance_I = 'IH | Habilitación de equipo' if t == 'I' else dic_trabajo_I[f"{i}.2.{equipo} I ({t}) | Alcance de la intervención"]

                        
                
                            # Asegurando que el serial pase de float a int
                            for llave, valor in dic_trabajo_I.items():
                                        if isinstance(valor,float):
                                            dic_trabajo_I[llave] = int(valor)


                            pdf_stream_I = informe_pdf_profesional(i, ot, tecnico, proyecto, fecha, cliente, tipo_I, modelo_I, serial_I, id, alcance_I, punto, obs_I, obs_generales, lista_imagenes, equipo)
                            
                            nombre_archivo_I = f"informe_OT-{ot}_{i}_{id}_{equipo}.pdf"

                            pdf_stream_I.seek(0)

                            try:
                                contenido_pdf = pdf_stream_I.read()
                                informe_codificado_I = base64.b64encode(contenido_pdf).decode('utf-8')
                            except FileNotFoundError:
                                exit()


                            
                            try:
                                equipment_I = odoo_client.search_read(
                                    'maintenance.equipment',
                                    [['serial_no', '=', serial_I]]
                                )
                                
                                if equipment_I:
                                    
                                    # Validamos si el equipo cuenta con una ubicación
                                    if equipment_I[0]['x_studio_location']:
                                        location_I = equipment_I[0]['x_studio_location'][1]
                                    else:
                                        location_I = False

                                    # Indentificación del dispositivo dentro de odoo
                                    number_equipment_I = equipment_I[0]['id']

                                    # Diccionarios de puntos
                                    puntos_odoo = odoo_client.search_read(
                                        'x_maintenance_location',
                                        [],
                                        fields=['id', 'x_name']
                                    )

                                    # Validamos que el punto marcado en el formulario exista en Odoo
                                    id_punto = None
                                    for p in puntos_odoo:
                                        if p['x_name'] == f'[{proyecto}] {punto}':
                                            id_punto = p['id']
                                            break
                                
                                    if not id_punto:

                                        detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                                f'{punto} no se encuentra listado en Odoo y Connecteam')

                                        inbox(ot, operators[tecnico], fecha, False, tipo_I, modelo_I, serial_I, id, odoo_client,
                                                f'{punto} no se encuentra listado en Odoo y Connecteam. Solicitar creación',
                                                'M',
                                                'Punto no existe en sistema',
                                                'Nuevo')

                                    # Si el equipo no tiene ubicación definida
                                    if location_I == False:
                                        
                                        # Búsqueda del punto dentro de la base de Odoo

                                        new_location_I = {
                                                'x_studio_location': id_punto,
                                                'assign_date': f"{fecha}",
                                            }

                                        # Actualizamos la ubicación en el perfil del equipo
                                        try:
                                            update_location_I = odoo_client.write(
                                                'maintenance.equipment',
                                                [number_equipment_I], 
                                                new_location_I
                                            )

                                            detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id,
                                                    f'Se asocia correctamente el dispositivo con el punto de monitoreo {punto}')                                       
                                            
                                        except:
                                            try:
                                                star_location = odoo_client.message_post(
                                                    'maintenance.equipment',
                                                    number_equipment_I,
                                                    f"<p><b>Ubicación de Instalación:</b> [{proyecto}] {punto}</p>"
                                                )
                                            except Exception as e:
                                                print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')
                                    

                                    elif location_I != f'[{proyecto}] {punto}' :
                                        
                                        new_location_I = {
                                            'x_studio_location': id_punto,
                                            'assign_date': f"{dic_trabajo_I['Fecha visita ']}",
                                        }

                                        
                                        try:

                                            # Actualización de la ubicación del equipo
                                            update_location_I = odoo_client.write(
                                                'maintenance.equipment',
                                                [number_equipment_I], 
                                                new_location_I
                                            )

                                            attachment_I = odoo_client.create(
                                                "ir.attachment",
                                                {
                                                    "name": nombre_archivo_I,
                                                    "type": "binary",
                                                    "datas": informe_codificado_I,
                                                    "res_model": 'maintenance.equipment',
                                                    "res_id": number_equipment_I,
                                                    "mimetype": "application/pdf",
                                                }
                                            )


                                            new_location = odoo_client.message_post(
                                                'maintenance.equipment',
                                                number_equipment_I, 
                                                f"<p><b>Cambio de ubicación:</b> {location_I} => [{proyecto}] {punto}</p><p><b>Ejecutor:</b> {tecnico}</p>",
                                                attachment_ids=[attachment_I]
                                            )
        
                        
                                            detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id, 
                                                        f'El dispositivo ahora se encuentra en [{proyecto}] {punto}')

                                            inbox(ot, operators[tecnico], fecha, id_punto, tipo_I, modelo_I, serial_I, id, odoo_client,
                                                    f'Equipo pasa de {location_I} a [{proyecto}] {punto}). Validar cambio {nombre_archivo_I}',
                                                    'N',
                                                    'Cambio de ubicación',
                                                    'En proceso')


                                            
                                        except Exception as e:
                                            print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')
                                    
                                    
                                    # Busqueda de solicitudes en proceso
                                    try:
                                        domain_filter = [['equipment_id', '=', number_equipment_I],
                                                        ['maintenance_type', '=', False],
                                                        ['x_studio_tipo_de_trabajo', '=', 'Instalación']] #Productivo: x_studio_tipo_trabajo

                                        request_ids_I = odoo_client.search(
                                            'maintenance.request',
                                            domain_filter,
                                        )
                                        
                                        # Iterando sobre las solicitudes que tiene el equipo
                                        if request_ids_I:
                                        

                                            # Buscamos que haya solicutudes en proceso    
                                            interest_requests_I = {} 
                                            for ids_I in request_ids_I:
                                                campos_de_interes_I = ['schedule_date', 'stage_id', 'name', 'archive']
                                                try:
                                                    request_data_I = odoo_client.read(
                                                        'maintenance.request',
                                                        [ids_I],
                                                        fields=campos_de_interes_I
                                                    )
                                                    
                                                    stage_id_I = request_data_I[0].get('stage_id') 
                                                    schedule_date_I = request_data_I[0].get('schedule_date')
                                                    name_I = request_data_I[0].get('name')
                                                    archived_I = request_data_I[0].get('archive')

                                                    # Solicitudes sin "Fecha programada" o "Archivadas"
                                                    if schedule_date_I == False or archived_I == True:
                                                        continue
                                                    # Solicitudes con fecha y finalizadas
                                                    elif schedule_date_I != False and stage_id_I[0] == 5: #Finalizado
                                                        continue
                                                    # Solicitudes con fecha y en desecho
                                                    elif schedule_date_I != False and stage_id_I[0] == 4: #Desechar
                                                        continue
                                                    else:
                                                        interest_requests_I[ids_I] = [schedule_date_I, stage_id_I, name_I]
                                                
                                                
                                                except Exception as e:
                                                    print(e)

                                            # Actualizamos la solicitud
                                            if interest_requests_I:
                                                id_I = list(interest_requests_I.keys())[0]
                                                

                                                # Finalizamos la tarjeta si se marca que la instalación es correcta 
                                                if operativo_I == "Sí":
                                                    try:
                                                        # Atualizando su estado a Finalizado
                                                        update_I = {
                                                            'stage_id': 5,
                                                            'x_studio_informe': informe_codificado_I,
                                                            'description': punto
                                                        }

                                                        update_stage_I = odoo_client.write(
                                                            'maintenance.request',
                                                            [id_I], 
                                                            update_I
                                                        )

                                                        close_date_I = {
                                                            'close_date': fecha,
                                                            'x_studio_tcnico': operators[tecnico]
                                                        }

                                                        update_close_date_I = odoo_client.write(
                                                            'maintenance.request',
                                                            [id_I], 
                                                            close_date_I)

                                                        
                                                        if update_stage_I:

                                                            detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id, 
                                                                        f'Se registra con exito el trabjo de instlación: {name_I}')

                                                            inbox(ot, operators[tecnico], fecha, id_punto, tipo_I, modelo_I, serial_I, id, odoo_client,
                                                                        'Se regista con exito el trabajo de instalación',
                                                                        'A',
                                                                        False,
                                                                        'Resuelto')
                                                                
                                                            # Actualización de bitácora
                                                            try:
                                                                actividad_id_I = odoo_client.search_read(
                                                                    'mail.activity',
                                                                    [['res_model', '=', 'maintenance.request'], ['res_id', '=', id_I]],
                                                                    limit=1
                                                                )

                                                                # Actualizando actividad
                                                                if actividad_id_I:
                                                                    try:
                                                                        actividad_number_I = actividad_id_I[0]['id']
                                                                        odoo_client.action_feedback(
                                                                            'mail.activity',
                                                                            [actividad_number_I],
                                                                            f"Instalación completada"
                                                                        )
                                                                        
                                                                    except Exception as e:
                                                                        print(f"Error al actualizar estado de la actividad de mantenimiento: {e}")

                                                            except Exception as e:
                                                                print(f"Error al listar de la actividad de mantenimiento: {e}")
                                                    
                                                            #  Buscamos el ID de la actividad existente para la OT

                                                    except Exception as e:
                                                        print(f"Error al actualizar estado de solicitud de mantenimiento MP: {e}")
                                                        traceback.print_exc()
                                                        continue
                                                
                                                # Se deja registro sobre la solicitud pues apun no se finalizan los trabajo
                                                else:

                                                    try:

                                                        actividad_id_I = odoo_client.search_read(
                                                            'mail.activity',
                                                            [['res_model', '=', 'maintenance.request'], ['res_id', '=', id_I]],
                                                            limit=1
                                                        )

                                                        # Actualizando actividad
                                                        if actividad_id_I:
                                                            try:
                                                                actividad_number_I = actividad_id_I[0]['id']
                                                                odoo_client.action_feedback(
                                                                    'mail.activity',
                                                                    [actividad_number_I])
                                                                
                                                            except Exception as e:
                                                                print(f"Error al actualizar estado de la actividad de mantenimiento: {e}")

                                                    except Exception as e:
                                                        print(f'Error al listar las activiades pendientes')


                                                    try:

                                                        attachment_I = odoo_client.create(
                                                            "ir.attachment",
                                                            {
                                                                "name": nombre_archivo_I,
                                                                "type": "binary",
                                                                "datas": informe_codificado_I,
                                                                "res_model": 'maintenance.request',
                                                                "res_id": id_I,
                                                                "mimetype": "application/pdf",
                                                            }
                                                        )

                                                        new_location = odoo_client.message_post(
                                                            'maintenance.request',
                                                            id_I, 
                                                            f"<p><b>Ubicación de trabajos:</b>[{proyecto}] {punto}</p><p><b>Ejecutor:</b> {tecnico}</p>",
                                                            attachment_ids=[attachment_I]
                                                        )
        

                                                    except Exception as e:
                                                        print(f'Error al notificar la actualización de la instalación: {e}')
                                            
                                            # Creación porque no hay solicitides en proceso  
                                            else:
                                                if operativo_I == 'Sí':
                                                    try:
                                                        fields_values_OT_I = {
                                                            'name': f"Instalación | {tipo_I} {modelo_I}",
                                                            'equipment_id': number_equipment_I, #Aquí debemos usar el ID númerico de la sonda
                                                            'stage_id': '5', # 5 Finalizado
                                                            'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                            # 'x_studio_etiqueta_1': id_mantencion[id],
                                                            'description': punto,
                                                            'schedule_date': fecha,
                                                            'x_studio_informe': informe_codificado_I
                                                        }

                                                        created_request_I = odoo_client.create(
                                                            'maintenance.request',
                                                            fields_values_OT_I
                                                        )

                                                        # Hacemos la escritura para que se actualice la fecha de cierre
                                                        update_stage_I = {
                                                            'stage_id': 5,
                                                        }

                                                        update_stage_I = odoo_client.write(
                                                            'maintenance.request',
                                                            [created_request_I], 
                                                            update_stage_I
                                                        )

                                                        update_close_date_I = {
                                                            'close_date': fecha,
                                                            'x_studio_tcnico': operators[tecnico]
                                                        }

                                                        update_close_date_I = odoo_client.write(
                                                            'maintenance.request',
                                                            [created_request_I], 
                                                            update_close_date_I
                                                        )

                                                        # Resgistro en resumen
                                                        
                                                        detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id,
                                                                    f'Se crea con éxito el registro de instalación {created_request_I}')
                                                        
                                                        inbox(ot, operators[tecnico], fecha, id_punto, tipo_I, modelo_I, serial_I, id, odoo_client,
                                                                    'Se crea con éxito el registro de instalación',
                                                                    'A',
                                                                    False,
                                                                    'Resuelto')

                                                        try:
                                                            # Buscamos el ID de la actividad existente para la OT_number
                                                            actividad_id_I = odoo_client.search_read(
                                                                'mail.activity',
                                                                [['res_model', '=', 'maintenance.request'], ['res_id', '=', created_request_I]],
                                                                limit=1
                                                            )

                                                            # Actualizando actividad
                                                            try:
                                                                actividad_number_I = actividad_id_I[0]['id']
                                                                odoo_client.action_feedback(
                                                                    'mail.activity',
                                                                    [actividad_number_I],
                                                                    f"Se ha instalado en el punto: {punto}"
                                                                )

                                                            except Exception as e:
                                                                print(f"Error al actualizar la actividad de instalación asociada: {e}")
                                                                continue        
                                                            
                                                        except Exception as e:
                                                            print(f"Error al buscar la actividad de instalación asociada: {e}") 
                                                            continue 

                                                    except Exception as e:
                                                        print(f'Error al crear el registro de instalación{e}')      

                                                else:
                                                    try:
                                                        fields_values_OT_I = {
                                                            'name': f"Instalación | {tipo_I} {modelo_I}",
                                                            'equipment_id': number_equipment_I, #Aquí debemos usar el ID númerico de la sonda
                                                            'stage_id': '3', # 5 Finalizado
                                                            'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                            # 'x_studio_etiqueta_1': id_mantencion[id],
                                                            'description': punto,
                                                            'schedule_date': fecha,
                                                        }

                                                        created_request_II = odoo_client.create(
                                                            'maintenance.request',
                                                            fields_values_OT_I
                                                        )
                                                        
                                                        detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id,
                                                                    f'Se crea con éxito el registro de instalación {created_request_I}')
                                                        
                                                        inbox(ot, operators[tecnico], fecha, id_punto, tipo_I, modelo_I, serial_I, id, odoo_client,
                                                                    'Se crea con éxito el registro de instalación',
                                                                    'A',
                                                                    False,
                                                                    'Resuelto')

                                                       

                                                        attachment_I = odoo_client.create(
                                                            "ir.attachment",
                                                            {
                                                                "name": nombre_archivo_I,
                                                                "type": "binary",
                                                                "datas": informe_codificado_I,
                                                                "res_model": 'maintenance.request',
                                                                "res_id": created_request_II,
                                                                "mimetype": "application/pdf",
                                                            }
                                                        )

                                                        new_location = odoo_client.message_post(
                                                            'maintenance.request',
                                                            created_request_II, 
                                                            f"<p><b>Ubicación de trabajos:</b>[{proyecto}] {punto}</p><p><b>Ejecutor:</b> {tecnico}</p>",
                                                            attachment_ids=[attachment_I]
                                                        )
                                                    


                                                    except Exception as e:
                                                        print(f'Error en la creación de la solicitud de instalación {e}')

                                        
                                        # Creación porque no hay solicitudes, ni terminadas ni en proceso, 
                                        else:
                                            if operativo_I == 'Sí':
                                                try:
                                                    fields_values_OT_I = {
                                                        'name': f"Instalación | {tipo_I} {modelo_I}",
                                                        'equipment_id': number_equipment_I, #Aquí debemos usar el ID númerico de la sonda
                                                        'stage_id': '5', # 5 Finalizado
                                                        'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                        # 'x_studio_etiqueta_1': id_mantencion[id],
                                                        'description': punto,
                                                        'schedule_date': fecha,
                                                        'x_studio_informe': informe_codificado_I
                                                    }

                                                    created_request_I = odoo_client.create(
                                                        'maintenance.request',
                                                        fields_values_OT_I
                                                    )

                                                    # Hacemos la escritura para que se actualice la fecha de cierre
                                                    update_stage_I = {
                                                        'stage_id': 5,
                                                    }

                                                    update_stage_I = odoo_client.write(
                                                        'maintenance.request',
                                                        [created_request_I], 
                                                        update_stage_I
                                                    )

                                                    update_close_date_I = {
                                                        'close_date': fecha,
                                                        'x_studio_tcnico': operators[tecnico]
                                                    }

                                                    update_close_date_I = odoo_client.write(
                                                        'maintenance.request',
                                                        [created_request_I], 
                                                        update_close_date_I
                                                    )

                                                    # Resgistro en resumen
                                                    
                                                    detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id,
                                                                f'Se crea con éxito el registro de instalación {created_request_I}')
                                                    
                                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_I, modelo_I, serial_I, id, odoo_client,
                                                                'Se crea con éxito el registro de instalación',
                                                                'A',
                                                                False,
                                                                'Resuelto')

                                                    try:
                                                        # Buscamos el ID de la actividad existente para la OT_number
                                                        actividad_id_I = odoo_client.search_read(
                                                            'mail.activity',
                                                            [['res_model', '=', 'maintenance.request'], ['res_id', '=', created_request_I]],
                                                            limit=1
                                                        )

                                                        # Actualizando actividad
                                                        try:
                                                            actividad_number_I = actividad_id_I[0]['id']
                                                            odoo_client.action_feedback(
                                                                'mail.activity',
                                                                [actividad_number_I],
                                                                f"Se ha instalado en el punto: {punto}"
                                                            )

                                                        except Exception as e:
                                                            print(f"Error al actualizar la actividad de instalación asociada: {e}")
                                                            continue        
                                                        
                                                    except Exception as e:
                                                        print(f"Error al buscar la actividad de instalación asociada: {e}") 
                                                        continue 

                                                except Exception as e:
                                                    print(f'Error al crear el registro de instalación{e}')      
                                            
                                            # Se marca que el equipo no queda operativo
                                            else:
                                                try:
                                                    fields_values_OT_I = {
                                                        'name': f"Instalación | {tipo_I} {modelo_I}",
                                                        'equipment_id': number_equipment_I, #Aquí debemos usar el ID númerico de la sonda
                                                        'stage_id': '3', # 5 Finalizado
                                                        'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                        # 'x_studio_etiqueta_1': id_mantencion[id],
                                                        'description': punto,
                                                        'schedule_date': fecha,
                                                    }

                                                    created_request_II = odoo_client.create(
                                                        'maintenance.request',
                                                        fields_values_OT_I
                                                    )
                                                    
                                                    detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id,
                                                                f'Se crea con éxito el registro de instalación {created_request_I}')
                                                    
                                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_I, modelo_I, serial_I, id, odoo_client,
                                                                'Se crea con éxito el registro de instalación',
                                                                'A',
                                                                False,
                                                                'Resuelto')

                                                    attachment_I = odoo_client.create(
                                                        "ir.attachment",
                                                        {
                                                            "name": nombre_archivo_I,
                                                            "type": "binary",
                                                            "datas": informe_codificado_I,
                                                            "res_model": 'maintenance.request',
                                                            "res_id": created_request_II,
                                                            "mimetype": "application/pdf",
                                                        }
                                                    )

                                                    new_location = odoo_client.message_post(
                                                        'maintenance.request',
                                                        created_request_II, 
                                                        f"<p><b>Ubicación de trabajos:</b>[{proyecto}] {punto}</p><p><b>Ejecutor:</b> {tecnico}</p>",
                                                        attachment_ids=[attachment_I]
                                                    )
                                            

                                                except Exception as e:
                                                    print(f'Error en la creación de la solicitud de instalación {e}')

                                    except Exception as e: 
                                        print(f"Error al obtener información de las solicitudes de instalaci´ón: {e}")
                                        continue 

                                else:
                                    
                                    try:
                                            sharepoint_client.upload_file(f'{SHAREPOINT_UPLOAD_INSTALL_BASE_URL}/{nombre_archivo_I}:/content', pdf_stream_I, "application/pdf" )
                                    except Exception as e:
                                            print(f"Error al subir el informe al Sharepoint: {e}")

                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id, 
                                                f'N° de serie no encontrado en Odoo. Revisar OT | {nombre_archivo_I}')
                                    

                                    punto_odoo = odoo_client.search_read(
                                        'x_maintenance_location',
                                        [['x_name', '=', f'[{proyecto}] {punto}']],
                                        limit=1
                                    )
                                    
                                    
                                    id_punto = punto_odoo[0]['id']

                                    if not id_punto:
                                        id_punto = False
                                        detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id, 
                                                f'{punto} no se encuentra listado en Odoo y Connecteam')

                                        inbox(ot, operators[tecnico], fecha, False, tipo_I, modelo_I, serial_I, id, odoo_client,
                                                f'{punto} no se encuentra listado en Odoo y Connecteam. Solicitar creación',
                                                'M',
                                                'Punto no existe en sistema',
                                                'Nuevo')

                                    #Validamos si el producto se encuntra instalado

                                    domain = [
                                        ('location_usage', '=', 'transit'),
                                        ('location_dest_usage', '=', 'customer'),
                                        ('lot_id.name', '=', serial_I),
                                        # ('reference', '=', 'WH/OUT/00189'),
                                        ('state', 'not in', ['done', 'cancel'])  # Filtra para que NO sea 'done' ni 'cancel'
                                    ]

                                    search_read = odoo_client.search_read(
                                        'stock.move.line',
                                        domain,
                                        limit=1
                                    )


                                    if search_read:
                                        inbox(ot, operators[tecnico], fecha, id_punto, tipo_I, modelo_I, serial_I, id, odoo_client,
                                                f'N° de serie no encontrado en Odoo. Revisar OT | {nombre_archivo_I}',
                                                'M',
                                                'Creación en espera',
                                                'Nuevo')
                                    else:
                                        inbox(ot, operators[tecnico], fecha, id_punto, tipo_I, modelo_I, serial_I, id, odoo_client,
                                                f'N° de serie no encontrado en Odoo. Revisar OT | {nombre_archivo_I}',
                                                'M',
                                                'S/N no encontrado',
                                                'Nuevo')

                            except Exception as e:
                                print(f"Error al buscar equipo en base de Odoo I: {e}")
                                traceback.print_exc()
                                
                            
                elif id == "MP":

                    # Iteramos sobre los tipos de mantenimientos
                    for t in MP_type:

                        for equipo in range(1, conteo_MP[t]+1):

                            filtro_MP = f"{i}.2.{equipo} MP ({t})"        
                            columnas_equipo_MP = df_trabajo.filter(like=filtro_MP).columns.to_list()
                            columnas_equipo_MP = ['#', 'user', f"{i}.1 Proyecto", 'Fecha visita ', 'Nombre del Cliente'] + columnas_equipo_MP
                            
                            # df trabajo se usa para la generación del informe
                            df_trabajo_equipo_MP = df_trabajo[columnas_equipo_MP]
                            dic_trabajo_MP = df_trabajo_equipo_MP.to_dict(orient='records')[0]

                            # Elmentos propios del equipo
                            modelo_MP = dic_trabajo_MP[f"{i}.2.{equipo} MP ({t}) | Modelo"]
                            tipo_MP = dic_trabajo_MP[f"{i}.2.{equipo} MP ({t}) | {MP_translate[t]} a intervenir"]
                            serial_MP = dic_trabajo_MP[f'{i}.2.{equipo} MP ({t}) | N° de serie']
                            operativo_MP = dic_trabajo_MP[f"{i}.2.{equipo} MP ({t}) | ¿{MP_translate[t]} operativo tras trabajos?"]
                            obs_MP = dic_trabajo_MP[f'{i}.2.{equipo} MP ({t}) | Observación']

                        
                
                            # Asegurando que el serial pase de float a int
                            for llave, valor in dic_trabajo_MP.items():
                                        if isinstance(valor,float):
                                            dic_trabajo_MP[llave] = int(valor)


                            pdf_stream_MP = informe_pdf_profesional(i, ot, tecnico, proyecto, fecha, cliente, tipo_MP, modelo_MP, serial_MP, id, False, punto, obs_MP, obs_generales, lista_imagenes, equipo)
                            
                            nombre_archivo_MP = f"informe_OT-{ot}_{i}_{id}_{t}_{equipo}.pdf"

                            pdf_stream_MP.seek(0)

                            try:
                                contenido_pdf = pdf_stream_MP.read()
                                informe_codificado_MP = base64.b64encode(contenido_pdf).decode('utf-8')
                            except FileNotFoundError:
                                exit()

                          

                        
                            # ACTUALIZACIÓN DE REQUEST
                            
                            # Buscamos las request que existan para el equipo en cuestión
                            try:
                                equipment_MP = odoo_client.search_read(
                                    'maintenance.equipment',
                                    [['serial_no', '=', serial_MP]],
                                    limit=1
                                )
                            
                                if equipment_MP:
                                    number_equipment_MP = equipment_MP[0]['id']

                                    # Validación de ubicación
                                    if equipment_MP[0]['x_studio_location']:
                                        location_MP = equipment_MP[0]['x_studio_location'][1]
                                    else:
                                        location_MP = False
                                    
                                    # Equipo a reparar sin una instancia de instalación
                                    puntos_odoo = odoo_client.search_read(
                                        'x_maintenance_location',
                                        [],
                                        fields=['id', 'x_name']
                                    )

                                    id_punto = None
                                    for p in puntos_odoo:
                                        if p['x_name'] == f'[{proyecto}] {punto}':
                                            id_punto = p['id']
                                            break
                                    

                                    if not id_punto:
                                        detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                                f'{punto} no se encuentra listado en Odoo y Connecteam')

                                        inbox(ot, operators[tecnico], fecha, False, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                f'{punto} no se encuentra listado en Odoo y Connecteam. Solicitar creación',
                                                'M',
                                                'Punto no existe en sistema',
                                                'Nuevo')
                                    

                                    if location_MP == False:

                                        try:
                                            star_location = odoo_client.message_post(
                                                'maintenance.equipment',
                                                number_equipment_MP,
                                                f"<p>Equipo sin evento de instalación We.</p><<p>Ubicación actual según OT-{ot}: {punto}</p>"
                                            )

                                            # trabajos sobre equipos que no estan con punto asignado
                                            inbox(ot, operators[tecnico], fecha, id_punto, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                f'Equipo sin evento de instalación We en el punto {punto}. Validar {nombre_archivo_MP}',
                                                'N',
                                                'Cambio de ubicación',
                                                'En proceso')
                                        
                                        except Exception as e:
                                            print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')
                        

                                    elif location_MP != f'[{proyecto}] {punto}':
                                        detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                                    f'Equipo pasa de {location_MP} a [{proyecto}] {punto}). Validar {nombre_archivo_MP}')
                                        
                                        # Notificación por cambio de ubicación

                                        try:
                                            
                                            new_location_MP = odoo_client.message_post(
                                                'maintenance.equipment',
                                                number_equipment_MP,
                                                f"<p><b>La ubicación a cambiado.</b></p><p><b>Nueva ubicación según OT-{ot}:</b> {location_MP} => [{proyecto}] {punto}</p>"
                                            )

                                            inbox(ot, operators[tecnico], fecha, id_punto, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                    f'Equipo pasa de {location_MP} a [{proyecto}] {punto}. Validar {nombre_archivo_MP}',
                                                    'N',
                                                    'Cambio de ubicación',
                                                    'En proceso')
                                                    
 
                                        except Exception as e:
                                            print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')  

                                    try:
                                        domain_filter = [['equipment_id', '=', number_equipment_MP],
                                                        ['maintenance_type', '=', 'preventive'],
                                                        ['x_studio_tipo_de_trabajo', '=', 'Mantención Preventiva']] #Productivo: x_studio_tipo_trabajo

                                        request_ids_MP = odoo_client.search(
                                            'maintenance.request',
                                            domain_filter,
                                        )
                                        
                                        # Iterando sobre las solicitudes que tiene el equipo
                                        if request_ids_MP:
                                        
                                            interruptor_MP = True   
                                            interest_requests_MP = {} 
                                            for ids_MP in request_ids_MP:
                                                campos_de_interes_MP = ['schedule_date', 'stage_id', 'name', 'archive']
                                                try:
                                                    request_data_MP = odoo_client.read(
                                                        'maintenance.request',
                                                        [ids_MP],
                                                        fields=campos_de_interes_MP
                                                    )
                                                    
                                                    stage_id_MP = request_data_MP[0].get('stage_id') 
                                                    schedule_date_MP = request_data_MP[0].get('schedule_date')
                                                    name_MP = request_data_MP[0].get('name')
                                                    archived_MP = request_data_MP[0].get('archive')

                                                    # Solicitudes sin "Fecha programada"
                                                    if schedule_date_MP == False or archived_MP == True:
                                                        continue
                                                    # Solicitudes con fecha y finalizadas
                                                    elif schedule_date_MP != False and stage_id_MP[0] == 5: #Finalizado
                                                        continue
                                                    # Solicitudes con fecha y en desecho
                                                    elif schedule_date_MP != False and stage_id_MP[0] == 4: #Desechar
                                                        continue
                                                    else:
                                                        interest_requests_MP[ids_MP] = [schedule_date_MP, stage_id_MP, name_MP]
                                                
                                                        interruptor_MP = False
                                                    
                                                except Exception as e:
                                                    print(e)

                                            # Buscamos la solicitud mas cercana a la fecha de realización del trabajo o aquella que se encuentra "en proceso"
                                            if interest_requests_MP:
                                                # Interruptor abierto por defecto para la no exitencia de un caso en proceso
                                                interruptor_MP = True
                                                id_MP = None

                                                for e in interest_requests_MP.keys():    
                                                    # Interruptor cerrado si encuentra un caso en proceso
                                                    if interest_requests_MP[e][1][0] == 3: #En proceso
                                                        interruptor_MP = False
                                                        id_MP = e
                                                        break
                                                
                                                # Si el interruptor sigue abierto, buscamos la solictud mas cercana a la fecha de realización del trabajo
                                                if interruptor_MP:
                                                    id_MP = min(interest_requests_MP.keys(), key=lambda x: abs(pd.to_datetime(interest_requests_MP[x][0]) - pd.to_datetime(fecha)))
                                                    
                                                    # Archivamos las solicitudes anteriores a la escogida
                                                    for x in interest_requests_MP.keys():
                                                        if interest_requests_MP[x][0] < interest_requests_MP[id_MP][0]:
                                                            try:
                                                                archive_MP = {
                                                                    'archive': True,
                                                                }
                                                                update_stage_MP = odoo_client.write(
                                                                    'maintenance.request',
                                                                    [x], 
                                                                    archive_MP
                                                                )
                                                            except Exception as e:
                                                                print(f"Error al archivar la solicitud {interest_requests_MP[x][2]}: {e}")
                                                            
                                                
                                                # Actualizamos el estado de la solicitud cuando el trabajo deja al equipo operativo
                                                if operativo_MP == "Sí":
                                                    try:
                                                        # Atualizando su estado a Finalizado
                                                        update_MP = {
                                                            'stage_id': 5,
                                                            'x_studio_informe': informe_codificado_MP,
                                                        }

                                                        update_stage_MP = odoo_client.write(
                                                            'maintenance.request',
                                                            [id_MP], 
                                                            update_MP
                                                        )

                                                        close_date_MP = {
                                                                'close_date': fecha
                                                        }
                                                        
                                                        update_close_date_MP = odoo_client.write(
                                                            'maintenance.request',
                                                            [id_MP], 
                                                            close_date_MP
                                                        )

                                                        
                                                        if update_stage_MP:
                                                            detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                                                        f'Se registra con exito el mantenimiento preventivo programado: {name_MP}')

                                                            inbox(ot, operators[tecnico], fecha, id_punto, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                                'Se registra con éxito el registro de mantenimiento',
                                                                'A',
                                                                False,
                                                                'Resuelto')
                                                                    
                                                            # Actualización de bitácora
                                                            try:
                                                                actividad_id_MP = odoo_client.search_read(
                                                                    'mail.activity',
                                                                    [['res_model', '=', 'maintenance.request'], ['res_id', '=', id_MP]],
                                                                    limit=1
                                                                )

                                                                # Actualizando actividad
                                                                if actividad_id_MP:
                                                                    try:
                                                                        actividad_number_MP = actividad_id_MP[0]['id']
                                                                        odoo_client.action_feedback(
                                                                            'mail.activity',
                                                                            [actividad_number_MP],
                                                                            f"<p><b>Se ha completado desde API</b></p><p>Última ubicación: {punto}</p>"
                                                                        )
                                                                        
                                                                    except Exception as e:
                                                                        print(f"Error al actualizar estado de la actividad de mantenimiento: {e}")

                                                            except Exception as e:
                                                                print(f"Error al listar de la actividad de mantenimiento: {e}")
                                                    
                                                            #  Buscamos el ID de la actividad existente para la OT
                                                                    
                                                    except Exception as e:
                                                        print(f"Error al actualizar estado de solicitud de mantenimiento MP: {e}")
                                                        traceback.print_exc()
                                                        continue
                                                
                                                # Actualizamos el estado de la solicitud cuando el trabajo no deja el equipo operativo
                                                elif operativo_MP == "No":
                                                    try:
                                                        # Atualizando su estado a en proceso
                                                        update_MP = {
                                                            'stage_id': 3,
                                                        }

                                                        update_stage_MP = odoo_client.write(
                                                            'maintenance.request',
                                                            [id_MP], 
                                                            update_MP
                                                        )   

                                                        if update_stage_MP:
                                                            detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                                                        f'Se registra con exito el mantenimiento preventivo programado: {name_MP}')

                                                            inbox(ot, operators[tecnico], fecha, id_punto, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                                'Se registra con éxito el registro de mantenimiento',
                                                                'A',
                                                                False,
                                                                'Resuelto')
                                                                                    
                                                        
                                                            attachment_MP = odoo_client.create(
                                                                "ir.attachment",
                                                                {
                                                                    "name": nombre_archivo_MP,
                                                                    "type": "binary",
                                                                    "datas": informe_codificado_MP,
                                                                    "res_model": 'maintenance.equipment',
                                                                    "res_id": id_MP,
                                                                    "mimetype": "application/pdf",
                                                                }
                                                            )

                                                            current_location_MP = odoo_client.message_post(
                                                                'maintenance.request',
                                                                id_MP,
                                                                f"<p><b>Ultima ubicación:</b> {punto}</p><p><b>Ejecutor:</b> {dic_trabajo_MP['user']}</p>",
                                                                attachment_ids=[attachment_MP]
                                                            )
                                                    except Exception as e:
                                                        print(f"Error al actualizar estado de solicitud de mantenimiento MP: {e}")
                                                        traceback.print_exc()
                                                        continue


                                            # Caso en que el equipo solo tiene solicitudes terminadas
                                            else:

                                                if operativo_MP == 'No':
                                                    try:
                                                        fields_values_OT_MP = {
                                                            'name': f"Mantenimiento Preventivo | {tipo_MP} {modelo_MP}",
                                                            'equipment_id': number_equipment_MP, #Aquí debemos usar el ID númerico de la sonda
                                                            'stage_id': '3', # 3 En proceso 
                                                            'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                            # 'x_studio_etiqueta_1': id_mantencion[id],
                                                            'schedule_date': f"{fecha}",
                                                            'description': obs_MP
                                                        }

                                                        created_request_MP = odoo_client.create(
                                                            'maintenance.request',
                                                            fields_values_OT_MP
                                                        )
                                                        
                                                        # Resgistro en resumen
                                                        detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id,
                                                                    f'Se crea con éxito el registro de mantenimiento {created_request_MP}')

                                                        inbox(ot, operators[tecnico], fecha, id_punto, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                                'Se crea con éxito el registro de mantenimiento',
                                                                'A',
                                                                False,
                                                                'Resuelto')
                                                
                                                        
                                                        attachment_MP = odoo_client.create(
                                                            "ir.attachment",
                                                            {
                                                                "name": nombre_archivo_MP,
                                                                "type": "binary",
                                                                "datas": informe_codificado_MP,
                                                                "res_model": 'maintenance.equipment',
                                                                "res_id": created_request_MP,
                                                                "mimetype": "application/pdf",
                                                            }
                                                        )

                                                        current_location_MP = odoo_client.message_post(
                                                            'maintenance.request',
                                                            created_request_MP,
                                                            f"<p><b>Ultima ubicación:</b> {punto}</p><p><b>Ejecutor:</b> {tecnico}</p>",
                                                            attachment_ids=[attachment_MP]
                                                        )

                                                        

                                                    except Exception as e:
                                                        print(f"Error al crear request MP para la OT-{dic_trabajo_MP['#']} en Odoo: {type(e)}")
                                                        print(traceback.format_exc())
                                                        continue

                                                # Se realiza el trabajo y queda operativo el dispositivo
                                                elif operativo_MP == 'Sí':
                                                    try:
                                                        fields_values_OT_MP = {
                                                            'name': f"Mantenimiento Correctivo | {tipo_MP} {modelo_MP}",
                                                            'equipment_id': number_equipment_MP, #Aquí debemos usar el ID númerico de la sonda
                                                            'stage_id': '5', # 5 Finalizado
                                                            'description': f"{obs_MP}",
                                                            'schedule_date': f"{fecha}",
                                                            'x_studio_informe': informe_codificado_MP,
                                                            'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                            # 'x_studio_etiqueta_1': id_mantencion[id],

                                                        }
                                                        created_request_MP = odoo_client.create(
                                                            'maintenance.request',
                                                            fields_values_OT_MP
                                                        )

                                                        # Hacemos la escritura para que se actualice la fecha de cierre
                                                        update_stage_MP = {
                                                            'stage_id': 5,
                                                        }

                                                        update_stage_MP = odoo_client.write(
                                                            'maintenance.request',
                                                            [created_request_MP], 
                                                            update_stage_MP
                                                        )

                                                        update_close_date_MP = {
                                                            'close_date': fecha,
                                                            'x_studio_tcnico': operators[tecnico]
                                                        }

                                                        update_close_date_MP = odoo_client.write(
                                                            'maintenance.request',
                                                            [created_request_MP], 
                                                            update_close_date_MP
                                                        )

                                                        # Resgistro en resumen
                                                        detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id,
                                                                    f'Se crea con éxito el registro de mantenimiento {created_request_MP}')

                                                        inbox(ot, operators[tecnico], fecha, id_punto, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                            'Se crea con éxito el registro de mantenimiento',
                                                            'A',
                                                            False,
                                                            'Resuelto')

                                                        
                                                        
                                                        # Actualización de la actividad por defecto 'Maintenance Request'
                                                        # Buscando el ID de la OT creada
                                                        id_MP = odoo_client.search(
                                                            'maintenance.request',
                                                            [['id', '=', created_request_MP]],
                                                            limit=1
                                                        )
                                                        
                                                        try:
                                                            # Buscamos el ID de la actividad existente para la OT_number
                                                            actividad_id_MP = odoo_client.search_read(
                                                                'mail.activity',
                                                                [['res_model', '=', 'maintenance.request'], ['res_id', '=', created_request_MP]],
                                                                limit=1
                                                            )

                                                            # Actualizando actividad
                                                            try:
                                                                actividad_number_MP = actividad_id_MP[0]['id']
                                                                odoo_client.action_feedback(
                                                                    'mail.activity',
                                                                    [actividad_number_MP],
                                                                    f"<p><b>Se ha completado desde API</b></p><p>Última ubicación: {punto}</p>"
                                                                )

                                                            except Exception as e:
                                                                print(f"Error al actualizar la actividad de mantenimiento asociada: {e}")
                                                                continue        
                                                            
                                                        except Exception as e:
                                                            print(f"Error al buscar la actividad de manteniminto asociada: {e}") 
                                                            continue   

                                                
                                                    except Exception as e:
                                                        print(f"Error al crear request MP para la OT-{dic_trabajo_MP['#']} en Odoo: {type(e)}")
                                                        print(traceback.format_exc())
                                                        continue
                                                
                                                # Sin plan de mantenimiento
                                                try:
                                                    sharepoint_client.upload_file(f'{SHAREPOINT_UPLOAD_BASE_URL}/{nombre_archivo_MP}:/content', pdf_stream_MP, "application/pdf" )
                                                except Exception as e:
                                                    print(f"Error al subir el informe al Sharepoint: {e}")
                                                    
                                                detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                                            f'Equipo sin plan de mantenimiennto en sistema')

                                                inbox(ot, operators[tecnico], fecha, id_punto, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                    f'Equipo sin plan de mantenimiennto en sistema',
                                                    'N',
                                                    'MP sin programar',
                                                    'En proceso')


                                        # Caso en que el equipo no tiene solicitudes de ninguna naturaleza 
                                             
                                        else:

                                            if operativo_MP == 'No':
                                                try:
                                                    fields_values_OT_MP = {
                                                        'name': f"Mantenimiento Preventivo | {tipo_MP} {modelo_MP}",
                                                        'equipment_id': number_equipment_MP, #Aquí debemos usar el ID númerico de la sonda
                                                        'stage_id': '3', # 3 En proceso 
                                                        'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                        # 'x_studio_etiqueta_1': id_mantencion[id],
                                                        'schedule_date': f"{fecha}",
                                                        'description': obs_MP
                                                    }

                                                    created_request_MP = odoo_client.create(
                                                        'maintenance.request',
                                                        fields_values_OT_MP
                                                    )
                                                    
                                                    # Resgistro en resumen
                                                    detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id,
                                                                f'Se crea con éxito el registro de mantenimiento {created_request_MP}')

                                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                            'Se crea con éxito el registro de mantenimiento',
                                                            'A',
                                                            False,
                                                            'Resuelto')
                                            
                                                    
                                                    attachment_MP = odoo_client.create(
                                                        "ir.attachment",
                                                        {
                                                            "name": nombre_archivo_MP,
                                                            "type": "binary",
                                                            "datas": informe_codificado_MP,
                                                            "res_model": 'maintenance.equipment',
                                                            "res_id": created_request_MP,
                                                            "mimetype": "application/pdf",
                                                        }
                                                    )

                                                    current_location_MP = odoo_client.message_post(
                                                        'maintenance.request',
                                                        created_request_MP,
                                                        f"<p><b>Ultima ubicación:</b> {punto}</p><p><b>Ejecutor:</b> {tecnico}</p>",
                                                        attachment_ids=[attachment_MP]
                                                    )

                                                    

                                                except Exception as e:
                                                    print(f"Error al crear request MP para la OT-{dic_trabajo_MP['#']} en Odoo: {type(e)}")
                                                    print(traceback.format_exc())
                                                    continue

                                            # Se realiza el trabajo y queda operativo el dispositivo
                                            elif operativo_MP == 'Sí':
                                                try:
                                                    fields_values_OT_MP = {
                                                        'name': f"Mantenimiento Preventivo | {tipo_MP} {modelo_MP}",
                                                        'equipment_id': number_equipment_MP, #Aquí debemos usar el ID númerico de la sonda
                                                        'stage_id': '5', # 5 Finalizado
                                                        'description': f"{obs_MP}",
                                                        'schedule_date': f"{fecha}",
                                                        'x_studio_informe': informe_codificado_MP,
                                                        'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                        # 'x_studio_etiqueta_1': id_mantencion[id],

                                                    }
                                                    created_request_MP = odoo_client.create(
                                                        'maintenance.request',
                                                        fields_values_OT_MP
                                                    )

                                                    # Hacemos la escritura para que se actualice la fecha de cierre
                                                    update_stage_MP = {
                                                        'stage_id': 5,
                                                    }

                                                    update_stage_MP = odoo_client.write(
                                                        'maintenance.request',
                                                        [created_request_MP], 
                                                        update_stage_MP
                                                    )

                                                    update_close_date_MP = {
                                                        'close_date': fecha,
                                                        'x_studio_tcnico': operators[tecnico]
                                                    }

                                                    update_close_date_MP = odoo_client.write(
                                                        'maintenance.request',
                                                        [created_request_MP], 
                                                        update_close_date_MP
                                                    )

                                                    # Resgistro en resumen
                                                    detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id,
                                                                f'Se crea con éxito el registro de mantenimiento {created_request_MP}')

                                                    inbox(ot, operators[tecnico], fecha, id_punto, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                        'Se crea con éxito el registro de mantenimiento',
                                                        'A',
                                                        False,
                                                        'Resuelto')

                                                    
                                                    
                                                    # Actualización de la actividad por defecto 'Maintenance Request'
                                                    # Buscando el ID de la OT creada
                                                    id_MP = odoo_client.search(
                                                        'maintenance.request',
                                                        [['id', '=', created_request_MP]],
                                                        limit=1
                                                    )
                                                    
                                                    try:
                                                        # Buscamos el ID de la actividad existente para la OT_number
                                                        actividad_id_MP = odoo_client.search_read(
                                                            'mail.activity',
                                                            [['res_model', '=', 'maintenance.request'], ['res_id', '=', created_request_MP]],
                                                            limit=1
                                                        )

                                                        # Actualizando actividad
                                                        try:
                                                            actividad_number_MP = actividad_id_MP[0]['id']
                                                            odoo_client.action_feedback(
                                                                'mail.activity',
                                                                [actividad_number_MP],
                                                                f"<p><b>Se ha completado desde API</b></p><p>Última ubicación: {punto}</p>"
                                                            )

                                                        except Exception as e:
                                                            print(f"Error al actualizar la actividad de mantenimiento asociada: {e}")
                                                            continue        
                                                        
                                                    except Exception as e:
                                                        print(f"Error al buscar la actividad de manteniminto asociada: {e}") 
                                                        continue   

                                            
                                                except Exception as e:
                                                    print(f"Error al crear request MP para la OT-{dic_trabajo_MP['#']} en Odoo: {type(e)}")
                                                    print(traceback.format_exc())
                                                    continue


                                            try:
                                                sharepoint_client.upload_file(f'{SHAREPOINT_UPLOAD_BASE_URL}/{nombre_archivo_MP}:/content', pdf_stream_MP, "application/pdf" )
                                            except Exception as e:
                                                print(f"Error al subir el informe al Sharepoint: {e}")
                                                
                                            detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                                        f'Equipo sin plan de mantenimiennto en sistema')

                                            inbox(ot, operators[tecnico], fecha, id_punto, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                f'Equipo sin plan de mantenimiennto en sistema',
                                                'N',
                                                'MP sin programar',
                                                'En proceso')
                                            
            
                                    except Exception as e: 
                                        print(f"Error al obtener información de la solicitudes de mantenimiento: {e}")
                                        continue 

                                else:   

                                    try:
                                        sharepoint_client.upload_file(f'{SHAREPOINT_UPLOAD_BASE_URL}/{nombre_archivo_MP}:/content', pdf_stream_MP, "application/pdf" )
                                    except Exception as e:
                                        print(f"Error al subir el informe al Sharepoint: {e}")

                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                                f'N° de serie no encontrado en Odoo. Revisar OT | {nombre_archivo_MP}')
                                    

                                    punto_odoo = odoo_client.search_read(
                                        'x_maintenance_location',
                                        [['x_name', '=', f'[{proyecto}] {punto}']],
                                        limit=1
                                    )

                                    id_punto = punto_odoo[0]['id']

                                    if not id_punto:
                                        id_punto = False
                                        detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                                f'{punto} no se encuentra listado en Odoo y Connecteam')

                                        inbox(ot, operators[tecnico], fecha, False, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                f'{punto} no se encuentra listado en Odoo y Connecteam. Solicitar creación',
                                                'M',
                                                'Punto no existe en sistema',
                                                'Nuevo')
                                        
                                    
                                    domain = [
                                        ('location_usage', '=', 'transit'),
                                        ('location_dest_usage', '=', 'customer'),
                                        ('lot_id.name', '=', serial_MP),
                                        # ('reference', '=', 'WH/OUT/00189'),
                                        ('state', 'not in', ['done', 'cancel'])  # Filtra para que NO sea 'done' ni 'cancel'
                                    ]

                                    search_read = odoo_client.search_read(
                                        'stock.move.line',
                                        domain,
                                        limit=1
                                    )


                                    if search_read:
                                        inbox(ot, operators[tecnico], fecha, id_punto, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                f'N° de serie no encontrado en Odoo. Revisar OT | {nombre_archivo_MP}',
                                                'M',
                                                'Creación en espera',
                                                'Nuevo')
                                    else:
                                        inbox(ot, operators[tecnico], fecha, id_punto, tipo_MP, modelo_MP, serial_MP, id, odoo_client,
                                                f'N° de serie no encontrado en Odoo. Revisar OT | {nombre_archivo_MP}',
                                                'M',
                                                'S/N no encontrado',
                                                'Nuevo')
                                    continue
                        
                            except Exception as e:
                                    print(f"Error al buscar equipo en base de Odoo MP: {e}")
                                    traceback.print_exc()
