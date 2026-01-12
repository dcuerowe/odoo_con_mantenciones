import re
import base64
import traceback
import pandas as pd
from datetime import datetime
from connecteam_api import user
from data_processing import detalle_op
from report_generator import informe_pdf_profesional
from config import SHAREPOINT_UPLOAD_BASE_URL, SHAREPOINT_UPLOAD_INSTALL_BASE_URL


def process_entrys(ordered_responses, API_key_c, resumen, exito, odoo_client, sharepoint_client):

    for df in ordered_responses:

        df = df.astype({'user': str}) #Eliminando las columnas que no se usaron
        
        df_con_datos = df.dropna(axis=1, how ='all') #Eliminando las columnas que no se usaron
        df_columnas = df_con_datos.columns.to_list() #Lista de columnas que si tienen datos

        index_user = df_con_datos.columns.get_loc('user')

        try:
            user_name = user(API_key_c, df_con_datos['user'][0])
        except Exception as e:
            user_name = "Usuario no encontrado"
            print(f"Error al obtener el nombre del usuario: {e}")
            traceback.print_exc()
        
        try:
            df_con_datos.iloc[0, index_user] = user_name # Añadir el nombre del usuario al DataFrame
        except Exception as e:
            print(f"Error al asignar el nombre del usuario al DataFrame: {e}")
            traceback.print_exc()


        #Elementos globales
        id_tipo_de_trabajo = ['MP', 'MC', 'I']
        
        id_mantencion = {'MC': 'Mantención Correctiva',
                        'MP': 'Mantención Preventiva',
                        'I': 'Instalación'}
        
        intalaciones_interes = ['Tablero', 'Caudalímetro', 'Sensor de nivel', 'Sonda multiparamétrica', 'Otro']

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
                tipos_realizados = [tipo.strip() for tipo in df_con_datos[f'{i}.2 Tipo de trabajo a realizar'][0].split(',') ]
            except:
                tipos_realizados = df_con_datos[f'{i}.2 Tipo de trabajo a realizar']

            # Columnas del punto {1} | general
            columnas_visita = [columna for columna in df_columnas if columna.startswith(i)]
            #columnas_visita.append(f'{i} Proyecto') 
            columnas_visita = ['#', 'user', 'Fecha visita ', 'Nombre del Cliente'] + columnas_visita 
            
            #Dejando un dataframe a nivel de visita de punto
            df_visita = df_con_datos[columnas_visita].copy()


            #Validando si el punto se encuentra seteadao en el listado de connecteam
            if df_visita[f'{i}.1 Punto de monitoreo'][0] == "No encontrado":
            
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
                    print(f"Error al procesar el punto de monitoreo en OT {df_visita['#'][0]}: {e}")
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

            #Definimos los ID de tipos de trabajo de interes
            id_tipos_interes = []
            for tipo in id_tipos_realizados:
                if tipo in id_tipo_de_trabajo:
                    id_tipos_interes.append(tipo)
            id_tipos_interes #[MC, MP]
            
            #Cantidad de MP realizadas
            MP_prefijo = set()
            for col in df_visita.columns:
                if ' MP |' in col: # Buscamos ' MP |' para identificar las columnas de MP
                    # Extraemos el prefijo como '1.2.1 MP' o '1.2.2 MP'
                    prefix_end_index = col.find(' MP |') + 4 # Sumamos 4 para incluir ' MP'
                    prefix = col[:prefix_end_index].strip()
                    MP_prefijo.add(prefix)
            
            conteo_instancias_MP = len(MP_prefijo)

            #Cantidad de MC realizadas
            MC_prefijo = set()
            for col in df_visita.columns:
                if ' MC |' in col: # Buscamos ' MC |' para identificar las columnas de MC
                    # Extraemos el prefijo como '1.2.1 MC' o '1.2.2 MC'
                    prefix_end_index = col.find(' MC |') + 4 # Sumamos 4 para incluir ' MC'
                    prefix = col[:prefix_end_index].strip()
                    MC_prefijo.add(prefix)
            
            conteo_instancias_MC = len(MC_prefijo)

            #Cantidad de I realizadas
            I_prefijo = set()
            for col in df_visita.columns:
                if ' I |' in col: # Buscamos ' MP |' para identificar las columnas de MP
                    # Extraemos el prefijo como '1.2.1 MP' o '1.2.2 MP'
                    I_prefix_end_index = col.find(' I |') + 4 # Sumamos 4 para incluir ' MP'
                    I_prefix = col[:I_prefix_end_index].strip()
                    I_prefijo.add(I_prefix)
            
            conteo_instancias_I = len(I_prefijo)



            for id in id_tipos_realizados:
                #Iniciamos la filtración por tipos de trabajo
                columnas_trabajo = [columna for columna in df_visita.columns if f'{id}' in columna]
                columnas_trabajo = ['#', 'user', f"{i}.1 Proyecto", 'Fecha visita ', 'Nombre del Cliente'] + columnas_trabajo
                df_trabajo = df_visita[columnas_trabajo]

                proyecto = df_visita[f"{i}.1 Proyecto"][0]
                punto = df_visita[f'{i}.1 Punto de monitoreo'][0]
                ot = df_visita['#'][0]
                fecha = df_visita['Fecha visita '][0]
                tecnico = df_visita['user'][0]
                
                #Tratamiento para Mantención correctiva
                if id == "MC":
                    for equipo in range(1, conteo_instancias_MC+1):
                        filtro_MC = f"{i}.2.{equipo} MC"        
                        columnas_equipo_MC = df_trabajo.filter(like=filtro_MC).columns.to_list()
                        columnas_equipo_MC = ['#', 'user', f"{i}.1 Proyecto", 'Fecha visita ', 'Nombre del Cliente'] + columnas_equipo_MC
                        df_trabajo_equipo_MC = df_trabajo[columnas_equipo_MC]
                        dic_trabajo_MC = df_trabajo_equipo_MC.to_dict(orient='records')[0]

                        #Elmentos propios del equipo
                        modelo_MC = dic_trabajo_MC[f"{i}.2.{equipo} MC | Modelo"]
                        tipo_MC = dic_trabajo_MC[f"{i}.2.{equipo} MC | ¿A qué se le realiza mantenimiento correctivo?"]
                        serial_MC = dic_trabajo_MC[f'{i}.2.{equipo} MC | N° de serie']
                        #operativo_MC = dic_trabajo_MC[f"{i}.2.{equipo} MC | ¿Equipo operativo?"]

                        
                        #Asegurando que el serial pase de float a int
                        for llave, valor in dic_trabajo_MC.items():
                                    if isinstance(valor,float):
                                        dic_trabajo_MC[llave] = int(valor)


                        pdf_stream_MC = informe_pdf_profesional(i, id, df_visita, df_trabajo_equipo_MC, equipo)
                        
                        nombre_archivo_MC = f"informe_OT-{df_visita['#'][0]}_{i}_{id}_{equipo}.pdf"

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

                                if location_MC == False:
                                    puntos_odoo = odoo_client.search_read(
                                        'x_maintenance_location',
                                        [],
                                        fields=['id', 'x_name']
                                    )
                                    #Lista de diccionarios

                                    id_punto = None
                                    for p in puntos_odoo:
                                        if p['x_name'] == df_con_datos[f'{i}.1 Punto de monitoreo'][0]:
                                            id_punto = p['id']
                                            break

                                    new_location_MC = {
                                        'x_studio_location': id_punto,
                                    # 'effective_date': f"{dic_trabajo_I['Fecha visita ']}",
                                    }

                                    try:
                                        update_location_MC = odoo_client.write(
                                            'maintenance.equipment',
                                            [id_number_MC], 
                                            new_location_MC
                                        )

                                        star_location = odoo_client.message_post(
                                            'maintenance.equipment',
                                            id_number_MC,
                                            f"<p>Ubicación asignada: {punto}</p>"
                                        )
                                        detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id,
                                                f'Se asocia correctamente el dispositico con el punto de monitoreo {punto}')

                                    except Exception as e:
                                        try:
                                            star_location = odoo_client.message_post(
                                                'maintenance.equipment',
                                                id_number_MC,
                                                f"<p>Nueva ubicación: {punto}</p>"
                                            )
                                        except Exception as e:
                                            print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')

                                        detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id, 
                                                    f'{punto} no se encuentra listado en Odoo y Connecteam({type(e)})')


                                if location_MC != df_con_datos[f'{i}.1 Punto de monitoreo'][0]:
                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id, 
                                                f'La ubicación indicada en la OT ({df_con_datos[f"{i}.1 Punto de monitoreo"][0]}) es distinta a la registrada en Odoo ({location_MC}). Revisar OT.')
                                    
                                    try:
                                        new_location_MC = odoo_client.message_post(
                                            'maintenance.equipment',
                                            id_number_MC,
                                            f"<p>La ubicación a cambiado.</p><p>Nueva ubicación: {punto}</p>"
                                        )
# Plasmar notificación de cambio de ubicación en el resumen
                                    except Exception as e:
                                        print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')  
            
                                else:
                                    try:
                                        last_location_MC = odoo_client.message_post(
                                            'maintenance.equipment',
                                            id_number_MC,
                                            f"<p>Última ubicación: {punto}</p>"
                                        )
                                    except Exception as e:
                                        print(f'Error al notificar la ubicación del equipo en Odoo: {e}')


                                #Busqueda de solicitues correctivas que mantiene el equipo
                                
                                try:
                                    domain_filter_MC = [['equipment_id', '=', id_number_MC],
                                                    ['maintenance_type', '=', 'corrective'],
                                                    ['x_studio_etiqueta_1', '=', 'Mantención Correctiva']]

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

                                        try:
                                            fields_values_OT_MC = {
                                                'name': f"Mantenimiento Correctivo | {tipo_MC} {modelo_MC}",
                                                'equipment_id': id_number_MC, #Aquí debemos usar el ID númerico de la sonda
                                                'stage_id': '5', # 5 Finalizado
                                                'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                #'x_studio_etiqueta_1': id_mantencion[id],
                                                'description': f"{dic_trabajo_MC[f'{i}.2.{equipo} MC | Observaciones']}",
                                                'schedule_date': f"{dic_trabajo_MC[f'Fecha visita ']}",
                                                'x_studio_informe': informe_codificado_MC,
                                                

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

#Registro de automatización exitosa                                            
                                            
                                            
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
                                                        f"Se ha completado desde API | Última ubicación: {punto}"
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

                                        #Sección que contempla los estados intermedios
                                        """
                                        if operativo_MC == 'No':
                                            try:
                                                fields_values_OT_MC = {
                                                    'name': f"Mantenimiento Correctivo | {tipo_MC} {modelo_MC}",
                                                    'equipment_id': id_number_MC, #Aquí debemos usar el ID númerico de la sonda
                                                    'stage_id': '3', # 3 En proceso 
                                                    'maintenance_type': id_mantencion[id],
                                                    'schedule_date': f"{dic_trabajo_MC[f'Fecha visita ']}",
                                                    #'close_date': f"{dic_trabajo_MC[f'Fecha visita ']}",
                                                    # 'maintenance_team_id': 1, #Equipo de mantenimiento por defecto
                                                    # 'user_id':  #Asignando el técnico que creó la solicitud
                                                    #'x_studio_nmero_de_ot_1': f"{dic_trabajo_MC['#']}"
                                                }
                                                created_request_MC = odoo_client.create(
                                                    'maintenance.request',
                                                    fields_values_OT_MC
                                                )
                                                
                                                #Resgistro en resumen
                                                detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id,
                                                            f'Se crea con éxito el registro de mantenimiento {created_request_MC}')
                                            
                                                  
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
                                                    f"<p><b>Ultima ubicación:</b> {punto}</p><p><b>Ejecutor:</b> {dic_trabajo_MC['user']}</p>",
                                                    attachment_ids=[attachment_MC]
                                                )

                                                


                                                #Actualización de bitácora

                                            except Exception as e:
                                                print(f"Error al crear request MC para la OT-{dic_trabajo_MC['#']} en Odoo: {type(e)}")
                                                print(traceback.format_exc())
                                                continue

                                        #------------------------------------------------------------------------
                                        # Se realiza el trabajo y queda operativo el dispositivo
                                        elif operativo_MC == 'Sí':
                                            try:
                                                fields_values_OT_MC = {
                                                    'name': f"Mantenimiento Correctivo | {tipo_MC} {modelo_MC}",
                                                    'equipment_id': id_number_MC, #Aquí debemos usar el ID númerico de la sonda
                                                    'stage_id': '5', # 5 Finalizado
                                                    'maintenance_type': id_mantencion[id],
                                                    'description': f"{dic_trabajo_MC[f'{i}.2.{equipo} MC | Observaciones']}",
                                                    'schedule_date': f"{dic_trabajo_MC[f'Fecha visita ']}",
                                                    'x_studio_informe': informe_codificado_MC,
                                                    #'close_date': f"{dic_trabajo_MC[f'Fecha visita ']}".split(' ')[0],
                                                    # 'maintenance_team_id': 1, #Equipo de mantenimiento por defecto
                                                    # 'user_id':  #Asignando el técnico que creó la solicitud
                                                    #'x_studio_nmero_de_ot_1': f"{dic_trabajo_MC['#']}"
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

                                                #Resgistro en resumen
                                                detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id,
                                                            f'Se crea con éxito el registro de mantenimiento {created_request_MC}')

                                                
                                                
                                                #Actualización de la actividad por defecto 'Maintenance Request'
                                                #Buscando el ID de la OT creada
                                                # id_MC = odoo_client.search(
                                                #     'maintenance.request',
                                                #     [['id', '=', created_request_MC]],
                                                #     limit=1
                                                # )
                                                
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
                                                            f"Se ha completado desde API | Última ubicación: {punto}"
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

                                        elif operativo_MC == 'Irrecuperable':
                                    
                                            try:
                                                fields_values_OT_MC = {
                                                    'name': f"Mantenimiento Correctivo | {tipo_MC} {modelo_MC}",
                                                    'equipment_id': id_number_MC, #Aquí debemos usar el ID númerico de la sonda
                                                    'stage_id': '4', # 4 Desechar
                                                    'maintenance_type': id_mantencion[id],
                                                    'schedule_date': f"{dic_trabajo_MC[f'Fecha visita ']}",
                                                    'x_studio_informe': informe_codificado_MC,
                                                    
                                                    # 'maintenance_team_id': 1, #Equipo de mantenimiento por defecto
                                                    # 'user_id':  #Asignando el técnico que creó la solicitud
                                                    #'x_studio_nmero_de_ot_1': f"{dic_trabajo_MC['#']}"
                                                }
                                                created_request_MC = odoo_client.create(
                                                    'maintenance.request',
                                                    fields_values_OT_MC
                                                )
                                                
                                                #Hacemos la escritura para que se actualice la fecha de cierre
                                                update_stage_MC = {
                                                    'stage_id': 4,
                                                }

                                                update_stage_MC = odoo_client.write(
                                                    'maintenance.request',
                                                    [created_request_MC], 
                                                    update_stage_MC
                                                )


                                                #Resgistro en resumen
                                                detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id,
                                                            f'Se crea con éxito el registro de mantenimiento {created_request_MC}')
                                                
                                                try:    
                                                    #Actualización de la actividad por defecto 'Maintenance Request'
                                                    #Buscando el ID de la OT creada
                                                    # Aca debemos incluir la gestión de estados a los dispositivos
                                                    # - Activo: Validado con el evento de intalación
                                                    # - Inactivo: Estado por defecto, hasta que no se concrete la instalación
                                                    # - Mantención: Siempre que mantenga algún mantenimento en estado 'En Proceso'
                                                    # - Desechado: Siempre que mantenga algún mantenimiento en estado 'Desechar'
                                                    
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
                                                            "<b>Equipo dado de baja</b>"
                                                        )

                                                    except Exception as e:
                                                        print(f"Error al actualizar la actividad de mantenimiento asociada: {e}")
                                                        continue        
                                                    
                                                except Exception as e:
                                                    print(f"Error al buscar la actividad de manteniminto asociada: {e}") 
                                                    continue 

                                                    
                                                    id_MC = odoo_client.search(
                                                        'maintenance.request',
                                                        [['id', '=', created_request_MC]],
                                                        limit=1
                                                    ) 
                                                   
                                                except Exception as e:
                                                    print(f"Error al buscar request de mantenimiento recien creada: {e}")
                                                    continue

                                                #Actualización de bitácora

                                            except Exception as e:
                                                print(f"Error al crear request MC para la OT-{dic_trabajo_MC['#']} en Odoo: {type(e)}")
                                                print(traceback.format_exc())
                                                continue
                                        """


                                    #------------------------------------------------------------------------
                                    #Actualización del request encontrado
                                    """
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
                                                
                                                if update_stage_MC:
                                                    detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MC, modelo_MC, serial_MC, id, 
                                                                f'Se registra con exito el mantenimiento correctivo pendiente: {ids_MC}')
                                                    
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
                                                                    f"Se ha completado desde API | Última ubicación: {punto}"
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
                                    """
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
                                continue
                        except Exception as e:
                            print(f"Error al buscar equipo en base de Odoo MC: {e}")
                            continue

                #Tratamiento para mantención preventiva  
                elif id == "MP":
                    for equipo in range(1,conteo_instancias_MP+1):
                        filtro_MP = f"{i}.2.{equipo} MP"
                        
                        columnas_equipo_MP = df_trabajo.filter(like=filtro_MP).columns.to_list()
                        columnas_equipo_MP = ['#', 'user', f"{i}.1 Proyecto", 'Fecha visita ', 'Nombre del Cliente'] + columnas_equipo_MP

                        df_trabajo_equipo_MP = df_trabajo[columnas_equipo_MP]

                        dic_trabajo_MP = df_trabajo_equipo_MP.to_dict(orient='records')[0]

                        for llave, valor in dic_trabajo_MP.items():
                            if isinstance(valor,float):
                                dic_trabajo_MP[llave] = int(valor)

                        modelo_MP = dic_trabajo_MP[f"{i}.2.{equipo} MP | Modelo"] 
                        tipo_MP = dic_trabajo_MP[f"{i}.2.{equipo} MP | ¿A qué se le realiza mantenimiento preventivo?"]
                        ot_mp = dic_trabajo_MP['#']
                        fecha_mp = dic_trabajo_MP['Fecha visita ']
                        #operativo_mp = dic_trabajo_MP[f"{i}.2.{equipo} MP | ¿Equipo operativo?"]


                        #print(df_trabajo_equipo_MP)
                        # CREACIÓN DE INFORME
                        pdf_stream_MP = informe_pdf_profesional(i, id, df_visita, df_trabajo_equipo_MP, equipo)
                        
                        nombre_archivo_MP = f"informe_OT-{df_visita['#'][0]}_{i}_{id}_{equipo}.pdf"

                        pdf_stream_MP.seek(0)


                        try:
                            contenido_pdf_MP = pdf_stream_MP.read()
                            informe_codificado_MP = base64.b64encode(contenido_pdf_MP).decode('utf-8')
                        except FileNotFoundError:
                            exit()

                        # with open(nombre_archivo_MP, 'wb') as f:
                        #     f.write(contenido_pdf_MP)


                        #ACTUALIZACIÓN DE REQUEST
                        
                        #Buscamos las request que existan para el equipo en cuestión
                        serial_MP = dic_trabajo_MP[f'{i}.2.{equipo} MP | N° de serie']
                        try:
                            equipment_MP = odoo_client.search_read(
                                'maintenance.equipment',
                                [['serial_no', '=', serial_MP]],
                                limit=1
                            )
                        
                            if equipment_MP:
                                number_equipment_MP = equipment_MP[0]['id']

                                #Validación de ubicación
                                if equipment_MP[0]['x_studio_location']:
                                    location_MP = equipment_MP[0]['x_studio_location'][1]
                                else:
                                    location_MP = False
                                

                                if location_MP != df_con_datos[f'{i}.1 Punto de monitoreo'][0]:
                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                    f'La ubicación indicada en la OT ({df_con_datos[f"{i}.1 Punto de monitoreo"][0]}) es distinta a la registrada en Odoo ({location_MP}). Revisar OT.')
                                        
                                    try:
                                        new_location_MP = odoo_client.message_post(
                                            'maintenance.equipment',
                                            number_equipment_MP,
                                            f"<p>La ubicación a cambiado.</p><p>Nueva ubicación: {punto}</p>"
                                        )
                                    except Exception as e:
                                        print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')                                    
                                    
                                else:
                                    try:
                                        last_location_MP = odoo_client.message_post(
                                            'maintenance.equipment',
                                            number_equipment_MP,
                                            f"<p>Última ubicación: {punto}</p>"
                                        )
                                    except Exception as e:
                                        print(f'Error al notificar la ubicación del equipo en Odoo: {e}')

                                try:
                                    domain_filter = [['equipment_id', '=', number_equipment_MP],
                                                    ['maintenance_type', '=', 'preventive'],
                                                    ['x_studio_etiqueta_1', '=', 'Mantención Preventiva']]

                                    request_ids_MP = odoo_client.search(
                                        'maintenance.request',
                                        domain_filter,
                                    )
                                    
                                    #Iterando sobre las solicitudes que tiene el equipo
                                    if request_ids_MP:
                                       
                                        # interruptor_MP = True   
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
                                            
                                                    # interruptor_MP = False
                                                
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
                                                id_MP = min(interest_requests_MP.keys(), key=lambda x: abs(pd.to_datetime(interest_requests_MP[x][0]) - pd.to_datetime(fecha_mp)))
                                                
                                                #Archivamos las solicitudes anteriores a la escogida
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
                                                        
                                            try:
                                                #Atualizando su estado a Finalizado
                                                update_MP = {
                                                    'stage_id': 5,
                                                    'x_studio_informe': informe_codificado_MP,
                                                    # 'x_studio_nmero_de_ot_1': f"{dic_trabajo_MP['#']}"
                                                }

                                                update_stage_MP = odoo_client.write(
                                                    'maintenance.request',
                                                    [id_MP], 
                                                    update_MP
                                                )
                                                
                                                if update_stage_MP:
                                                    detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                                                f'Se registra con exito el mantenimiento preventivo programado: {name_MP}')
                                                    
                                                    #Actualización de bitácora
                                                    try:
                                                        actividad_id_MP = odoo_client.search_read(
                                                            'mail.activity',
                                                            [['res_model', '=', 'maintenance.request'], ['res_id', '=', id_MP]],
                                                            limit=1
                                                        )

                                                        #Actualizando actividad
                                                        if actividad_id_MP:
                                                            try:
                                                                actividad_number_MP = actividad_id_MP[0]['id']
                                                                odoo_client.action_feedback(
                                                                    'mail.activity',
                                                                    [actividad_number_MP],
                                                                    f"Se ha completado desde API | Última ubicación: {punto}"
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
                                        
                                            """
                                            #Actualizamos el estado de la solicitud cuando el trabajo deja al equipo operativo
                                            if operativo_mp == "Sí":
                                                try:
                                                    #Atualizando su estado a Finalizado
                                                    update_MP = {
                                                        'stage_id': 5,
                                                        'x_studio_informe': informe_codificado_MP,
                                                        # 'x_studio_nmero_de_ot_1': f"{dic_trabajo_MP['#']}"
                                                    }

                                                    update_stage_MP = odoo_client.write(
                                                        'maintenance.request',
                                                        [id_MP], 
                                                        update_MP
                                                    )
                                                    
                                                    if update_stage_MP:
                                                        detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                                                    f'Se registra con exito el mantenimiento preventivo programado: {name_MP}')
                                                        
                                                        #Actualización de bitácora
                                                        try:
                                                            actividad_id_MP = odoo_client.search_read(
                                                                'mail.activity',
                                                                [['res_model', '=', 'maintenance.request'], ['res_id', '=', id_MP]],
                                                                limit=1
                                                            )

                                                            #Actualizando actividad
                                                            if actividad_id_MP:
                                                                try:
                                                                    actividad_number_MP = actividad_id_MP[0]['id']
                                                                    odoo_client.action_feedback(
                                                                        'mail.activity',
                                                                        [actividad_number_MP],
                                                                        f"Se ha completado desde API | Última ubicación: {punto}"
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
                                            
                                            #Actualizamos el estado de la solicitud cuando el trabajo no deja el equipo operativo
                                            elif operativo_mp == "No":
                                                try:
                                                    #Atualizando su estado a en proceso
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
                                                    
                                                        attachment_MP = odoo_client.create(
                                                            "ir.attachment",
                                                            {
                                                                "name": nombre_archivo_MP,
                                                                #"type": "binary",
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
                                            """  
                                        #Creación de MP        
                                        else:

                                            try:
                                                fields_values_OT_MP = {
                                                    'name': f"Mantenimiento Preventivo | {tipo_MP} {modelo_MP}",
                                                    'equipment_id': number_equipment_MP, #Aquí debemos usar el ID númerico de la sonda
                                                    'stage_id': '5', # 5 Finalizado
                                                    'x_studio_tipo_de_trabajo': id_mantencion[id],
                                                    #'x_studio_etiqueta_1': id_mantencion[id],
                                                    'description': f"{dic_trabajo_MP[f'{i}.2.{equipo} MP | Observaciones']}",
                                                    'schedule_date': f"{dic_trabajo_MP[f'Fecha visita ']}",
                                                    'x_studio_informe': informe_codificado_MP,
                                                    

                                                }
                                                created_request_MP = odoo_client.create(
                                                    'maintenance.request',
                                                    fields_values_OT_MP
                                                )

                                                #Hacemos la escritura para que se actualice la fecha de cierre
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

                                                #Resgistro en resumen
                                                print(id_mantencion[id])
                                                detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id,
                                                            f'Se crea con éxito el registro de mantenimiento {created_request_MP}')

    #Registro de automatización exitosa                                 4           
                                                

                                                
                                                try:
                                                    #Buscamos el ID de la actividad existente para la OT_number
                                                    actividad_id_MP = odoo_client.search_read(
                                                        'mail.activity',
                                                        [['res_model', '=', 'maintenance.request'], ['res_id', '=', created_request_MP]],
                                                        limit=1
                                                    )

                                                    #Actualizando actividad
                                                    try:
                                                        actividad_number_MP = actividad_id_MP[0]['id']
                                                        odoo_client.action_feedback(
                                                            'mail.activity',
                                                            [actividad_number_MP],
                                                            f"Se ha completado desde API | Última ubicación: {punto}"
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

                                            try:
                                                sharepoint_client.upload_file(f'{SHAREPOINT_UPLOAD_BASE_URL}/{nombre_archivo_MP}:/content', pdf_stream_MP, "application/pdf" )
                                            except Exception as e:
                                                print(f"Error al subir el informe al Sharepoint: {e}")
# Notificación de falta de plan de mantenimiento preventivo
                                            detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                                        f'El equipo/instrumento no cuenta con una solicitud de mantenimiento preventivo programada. Revisar OT | {nombre_archivo_MP}')

                                    else:

                                        try:
                                            sharepoint_client.upload_file(f'{SHAREPOINT_UPLOAD_BASE_URL}/{nombre_archivo_MP}:/content', pdf_stream_MP, "application/pdf" )
                                        except Exception as e:
                                            print(f"Error al subir el informe al Sharepoint: {e}")

                                        detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_MP, modelo_MP, serial_MP, id, 
                                                    f'El equipo no tiene un plan de mantenimiento cargado en Odoo. Revisar OT | {nombre_archivo_MP}')
        
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
                                continue
                    
                        except Exception as e:
                                    print(f"Error al buscar equipo en base de Odoo MP: {e}")
                
                #Tratamiento para Instalaciones
                elif id == "I":
                    for equipo in range(1, conteo_instancias_I+1):
                        filtro_I = f"{i}.2.{equipo} I"        
                        columnas_equipo_I = df_trabajo.filter(like=filtro_I).columns.to_list()
                        columnas_equipo_I = ['#', 'user', f"{i}.1 Proyecto", 'Fecha visita ', 'Nombre del Cliente'] + columnas_equipo_I
                        df_trabajo_equipo_I = df_trabajo[columnas_equipo_I]
                        dic_trabajo_I = df_trabajo_equipo_I.to_dict(orient='records')[0]
                
                        modelo_I = dic_trabajo_I[f"{i}.2.{equipo} I | Modelo"]
                        tipo_I = dic_trabajo_I[f"{i}.2.{equipo} I | Tipo de equipo/instrumento a instalar"]


                        pdf_stream_I = informe_pdf_profesional(i, id, df_visita, df_trabajo_equipo_I, equipo)

                        
                        nombre_archivo_I = f"informe_OT-{df_visita['#'][0]}_{i}_{id}_{equipo}.pdf"

                        pdf_stream_I.seek(0)

                        try:
                            contenido_pdf_I = pdf_stream_I.read()
                            informe_codificado_I = base64.b64encode(contenido_pdf_I).decode()
                        except FileNotFoundError:
                            exit()


                        #print(dic_trabajo_I)
                        #Busqueda del ID del equipo en la base de datos maintenance.equipment
                        if tipo_I in intalaciones_interes:
                            serial_I = dic_trabajo_I[f'{i}.2.{equipo} I | N° de serie']
                            try:
                                equipment_I = odoo_client.search_read(
                                    'maintenance.equipment',
                                    [['serial_no', '=', serial_I]]
                                )
                                
                                if equipment_I:

                                    if equipment_I[0]['x_studio_location']:
                                        location_I = equipment_I[0]['x_studio_location'][1]
                                    else:
                                        location_I = False

                                    number_equipment_I = equipment_I[0]['id']


                                    # Si el equipo no tiene ubicación definida
                                    if location_I == False:
                                        
                                        #Busqueda del punto dentro de la bas de Odoo
                                        puntos_odoo = odoo_client.search_read(
                                            'x_maintenance_location',
                                            [],
                                            fields=['id', 'x_name']
                                        )
                                        #Lista de diccionarios

                                        id_punto = None
                                        for p in puntos_odoo:
                                            if p['x_name'] == df_con_datos[f'{i}.1 Punto de monitoreo'][0]:
                                                id_punto = p['id']
                                                break
                                        
                                        if not id_punto:
                                            print(f'Punto no encontrado: {df_con_datos[f"{i}.1 Punto de monitoreo"][0]}')
                                                   
# Aqui generamos la instancia de punto no encontrado

                                        new_location_I = {
                                            'x_studio_location': id_punto,
                                            'assign_date': f"{dic_trabajo_I['Fecha visita ']}",
                                        }

                                        try:
                                            update_location_I = odoo_client.write(
                                                'maintenance.equipment',
                                                [number_equipment_I], 
                                                new_location_I
                                            )

                                            detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id,
                                                    f'Se asocia correctamente el dispositivo con el punto de monitoreo {punto}')
#Notificación de éxito                                         
                                            
                                        except Exception as e:

                                            try:
                                                star_location = odoo_client.message_post(
                                                    'maintenance.equipment',
                                                    number_equipment_I,
                                                    f"<p>Nueva ubicación: {punto}</p><p>: {dic_trabajo_I['Fecha visita ']} </p>"
                                                )
                                            except Exception as e:
                                                print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')

                                    
                                    # Si la ubicación del equipo cambia
                                    elif location_I != df_con_datos[f'{i}.1 Punto de monitoreo'][0]:
#Notificación de cambio de ubicación
                                        
                                        detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id, 
                                                    f'El dispositivo ahora se encuentra en {punto}')
        
                                        try:
                                            new_location = odoo_client.message_post(
                                                'maintenance.equipment',
                                                number_equipment_I,
                                                f"<p>La ubicación a cambiado.</p><p>Nueva ubicación: {punto}</p>",
                                                attachment_ids=[attachment_id]
                                            )
                                            
                                        except Exception as e:
                                            print(f'Error al notificar la nueva ubicación del equipo en Odoo: {e}')
                                    
                                    
                                    # Creamos la instancia dentro de Odoo
                                    fields_values_OT_I = {
                                        'name': f"Instalación | {tipo_I} {modelo_I}",
                                        'equipment_id': number_equipment_I, #Aquí debemos usar el ID númerico de la sonda
                                        'stage_id': '5', # 5 Finalizado
                                        'x_studio_tipo_de_trabajo': id_mantencion[id],
                                        #'x_studio_etiqueta_1': id_mantencion[id],
                                        'description': punto,
                                        'schedule_date': f"{fecha}",
                                        'x_studio_informe': informe_codificado_I,
                                    }

                                    try:                                             
                                        created_request_I = odoo_client.create(
                                            'maintenance.request',
                                            fields_values_OT_I
                                        )

                                        #Hacemos la escritura para que se actualice la fecha de cierre
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

                                        #Resgistro en resumen
                                        print(id_mantencion[id])
                                        detalle_op(exito, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id,
                                                    f'Se crea con éxito el registro de instalación {created_request_I}')
                                        
                                    
                                        try:
                                            #Buscamos el ID de la actividad existente para la OT_number
                                            actividad_id_I = odoo_client.search_read(
                                                'mail.activity',
                                                [['res_model', '=', 'maintenance.request'], ['res_id', '=', created_request_I]],
                                                limit=1
                                            )

                                            #Actualizando actividad
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
                                        print(f'Error al crear el registro de instalación: {e}')
                                        detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id,
                                                    f'Error al crear el registro de instalación: {e}')


                                else:
                                    try:
                                        pdf_stream_I.seek(0)
                                        sharepoint_client.upload_file(f'{SHAREPOINT_UPLOAD_INSTALL_BASE_URL}/{nombre_archivo_I}:/content', pdf_stream_I, "application/pdf" )

                                    except Exception as e:
                                        print(f"Error al subir el informe al Sharepoint: {e}")

                                    detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, serial_I, id,
                                                f'N° de serie no encontrado en Odoo. | Revisar OT {nombre_archivo_I}')
                                    continue
                                            
                            except Exception as e:
                                print(f"Error al buscar equipo en base de Odoo I: {type(e)}")
                                traceback.print_exc()
                                
                                continue
                        else:
                            detalle_op(resumen, ot, tecnico, fecha, proyecto, punto, tipo_I, modelo_I, 'No solicitado', id,
                                    f'Equipo/instrumento no considerado dentro del modulo de mantención')
