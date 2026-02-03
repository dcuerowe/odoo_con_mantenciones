import time
import schedule
import pandas as pd
import tabulate
import sqlite3
import os
from config import (
    ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD,
    SHAREPOINT_USER, SHAREPOINT_PASSWORD, SHAREPOINT_SITE, SHAREPOINT_NAME_SITE, SHAREPOINT_DOC_LIBRARY,
    CONNECTEAM_API_KEY
)
from sharepoint_client import Sharepoint
from odoo_client import OdooClient
from connecteam_api import all_submission, filter_submissions, form_structure
from data_processing import ordenar_respuestas, check_new_sub
from processor import process_entrys
from excel_manager import send_data

def job():
    print('\n-> Detección automática de OTs en Connecteam')
    
    # Initialize Clients
    sp = Sharepoint()
    odoo = OdooClient(ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD)
    try:
        odoo.authenticate()
    except Exception as e:
        print(f"Error authenticating with Odoo: {e}")
        return

    try:
        # Obtiene la estructura del formulario y las submissions filtradas, luego las ordena
        ordered_responses_2 = ordenar_respuestas(form_structure(CONNECTEAM_API_KEY), filter_submissions(CONNECTEAM_API_KEY))
    except Exception as e:
        # Si ocurre un error en la conexión a la API, lo muestra
        print(f"Ocurrio un problema con la conexión a la API-Connecteam: {e}")
        return

    print(f"\n[{time.ctime()}] Buscando nuevas entradas...")
    try:
        # Busca nuevas OTs que no hayan sido procesadas previamente
        nuevas_entradas = check_new_sub(ordered_responses_2)
        if nuevas_entradas:
            # Inicializa los diccionarios para resumen y éxito de operaciones
            resumen = {
                'OT': [], 'Técnico': [], 'Fecha de revisión': [], 'Proyecto': [],
                'Punto de monitoreo': [], 'Equipo/instrumento': [], 'Modelo': [],
                'N° serie': [], 'Tipo': [], 'Mensaje': []
            }
            exito = {
                'OT': [], 'Técnico': [], 'Fecha de revisión': [], 'Proyecto': [],
                'Punto de monitoreo': [], 'Equipo/instrumento': [], 'Modelo': [],
                'N° serie': [], 'Tipo': [], 'Mensaje': []
            }

            print(f"Se encontraron {len(nuevas_entradas)} nuevas entradas. Procesando...")
            # Procesa las nuevas entradas encontradas
            process_entrys(nuevas_entradas, CONNECTEAM_API_KEY, resumen, exito, odoo, sp)

            # Convierte los diccionarios a DataFrames para facilitar el manejo de datos
            df_resumen = pd.DataFrame(resumen)
            df_exito = pd.DataFrame(exito)

            # Filtra las operaciones que requieren tratamiento manual por tipo de trabajo
            df_manual_m = df_resumen[(df_resumen['Tipo'] == 'MC') | (df_resumen['Tipo'] == 'MP')]
            df_manual_i = df_resumen[df_resumen['Tipo'] == 'I']

            try:
                # Envía los datos filtrados a SharePoint, actualizando los archivos correspondientes
                send_data(df_manual_i, 'Instalaciones', 'resumen_instalación', sp)
                send_data(df_manual_m, 'Mantenciones', 'resumen_mantenciones', sp)

                # Muestra por consola los resúmenes de operaciones manuales y exitosas
                print("\nResumen de operaciones para tratamiento manual:")
                print(tabulate.tabulate(df_resumen, headers='keys', tablefmt='grid'))

                print("\nResumen de operaciones exitosas:")
                print(tabulate.tabulate(df_exito, headers='keys', tablefmt='grid'))

            except Exception as e:
                # Si ocurre un error al actualizar SharePoint, lo muestra
                print(f"Error al actualizar sharepoint: {e}")

    except Exception as e:
        # Si ocurre un error durante la ejecución de la tarea, lo muestra
        print(f"Ocurrió un error durante la ejecución de la tarea: {e}")


def main():
    # Initialize Clients
    sp = Sharepoint()
    odoo = OdooClient(ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD)
    try:
        odoo.authenticate()
    except Exception as e:
        print(f"Error authenticating with Odoo: {e}")
        # We continue, but Odoo calls will fail. 
        # In a real app we might want to exit or retry.

    while True:
        print('\nTipo de ejecución a realizar')
        print('----------------------------')
        print('(1) OTs específicas')
        print('(2) Revisión al día de hoy')
        print('(3) Detección automática de OTs')
        print('(4) Salir')

        codigo = input('\nIndique un código: ')

        if codigo == '1':
            resumen = {
                'OT': [], 'Técnico': [], 'Fecha de revisión': [], 'Proyecto': [],
                'Punto de monitoreo': [], 'Equipo/instrumento': [], 'Modelo': [],
                'N° serie': [], 'Tipo': [], 'Mensaje': []
            }
            exito = {
                'OT': [], 'Técnico': [], 'Fecha de revisión': [], 'Proyecto': [],
                'Punto de monitoreo': [], 'Equipo/instrumento': [], 'Modelo': [],
                'N° serie': [], 'Tipo': [], 'Mensaje': []
            }

            print('\nIndique las OTs a procesar (separadas por espacio): ')
            lista_ot = input('#: ').split(' ')
            try:
                ot = [int(i) for i in lista_ot]
            except ValueError:
                print("Entrada inválida. Por favor ingrese números.")
                continue
            try:
                ordered_responses_1 = ordenar_respuestas(form_structure(CONNECTEAM_API_KEY), all_submission(CONNECTEAM_API_KEY))
            except Exception as e:
                print(f"Ocurrio un problema con la conexión a la API-Connecteam: {e}")
                traceback.print_exc()
                continue
            
            sublista_1 = ordered_responses_1[ordered_responses_1['#'].isin(ot)]

            
            process_entrys(sublista_1, CONNECTEAM_API_KEY, resumen, exito, odoo, sp)


            df_resumen = pd.DataFrame(resumen)
            df_exito = pd.DataFrame(exito)

            #definimos aquellos mensajes por mantención e instalación que requieren actualización manual
            df_manual_m = df_resumen[(df_resumen['Tipo'] == 'MC') | (df_resumen['Tipo'] == 'MP')]
            df_manual_i = df_resumen[df_resumen['Tipo'] == 'I']

            # try:
            #     #send_data(df_manual_i, 'Instalaciones', 'resumen_instalación', sp)
            #     #send_data(df_manual_m, 'Mantenciones', 'resumen_mantenciones', sp)

            #     try:    
            #         #Validandoq que ya no se haya procesaso la OT indicada
            #         with sqlite3.connect('form_entries.db') as connection:
            #             cursor = connection.cursor()

            #             for entry in ot:
            #                 cursor.execute("INSERT OR IGNORE INTO processed_entries (entry_id) VALUES (?)", (entry,))
            #                 print(f"\n-> ID {entry} guardado en la base de datos.")

            #     except Exception as e:
            #         print(f"Problemas para actualizar base de datos de OTs revisadas: {e}")
            
            # except Exception as e:
            #     print(f"Error al actualizar sharepoint: {e}")
            
            print("\nResumen de operaciones para tratamiento manual:")
            print(tabulate.tabulate(df_resumen, headers='keys', tablefmt='grid'))

            print("\nResumen de operaciones exitosas:")
            print(tabulate.tabulate(df_exito, headers='keys', tablefmt='grid'))

        # elif codigo == '2':
        #     try:
        #         #Provisorio
        #         data = pd.read_excel('OT_borrador_2.xlsx')
        #         data_list = [data]
        #         #ordered_responses_3 = ordenar_respuestas(form_structure(CONNECTEAM_API_KEY), all_submission(CONNECTEAM_API_KEY))
        #     except Exception as e:
        #         print(f"Ocurrio un problema con la conexión a la API-Connecteam: {e}")
        #         continue
        
        #     try:
        #     # Busca nuevas OTs que no hayan sido procesadas previamente
        #         # nuevas_entradas = check_new_sub(data_list)
        #         # if nuevas_entradas:
        #         #     # Inicializa los diccionarios para resumen y éxito de operaciones
        #         #     resumen = {
        #         #         'OT': [], 'Técnico': [], 'Fecha de revisión': [], 'Proyecto': [],
        #         #         'Punto de monitoreo': [], 'Equipo/instrumento': [], 'Modelo': [],
        #         #         'N° serie': [], 'Tipo': [], 'Mensaje': []
        #         #     }
        #         #     exito = {
        #         #         'OT': [], 'Técnico': [], 'Fecha de revisión': [], 'Proyecto': [],
        #         #         'Punto de monitoreo': [], 'Equipo/instrumento': [], 'Modelo': [],
        #         #         'N° serie': [], 'Tipo': [], 'Mensaje': []
        #         #     }

        #         #     print(f"Se encontraron {len(nuevas_entradas)} nuevas entradas. Procesando...")
        #         #     # Procesa las nuevas entradas encontradas
        #             process_entrys(nuevas_entradas, CONNECTEAM_API_KEY, resumen, exito, odoo, sp)

        #             # Convierte los diccionarios a DataFrames para facilitar el manejo de datos
        #             df_resumen = pd.DataFrame(resumen)
        #             df_exito = pd.DataFrame(exito)

        #             # Filtra las operaciones que requieren tratamiento manual por tipo de trabajo
        #             df_manual_m = df_resumen[(df_resumen['Tipo'] == 'MC') | (df_resumen['Tipo'] == 'MP')]
        #             df_manual_i = df_resumen[df_resumen['Tipo'] == 'I']

        #             try:
        #                 # Envía los datos filtrados a SharePoint, actualizando los archivos correspondientes
        #                 #send_data(df_manual_i, 'Instalaciones', 'resumen_instalación', sp)
        #                 #send_data(df_manual_m, 'Mantenciones', 'resumen_mantenciones', sp)                    

        #                 # Muestra por consola los resúmenes de operaciones manuales y exitosas
        #                 print("\nResumen de operaciones para tratamiento manual:")
        #                 print(tabulate.tabulate(df_resumen, headers='keys', tablefmt='grid'))

        #                 print("\nResumen de operaciones exitosas:")
        #                 print(tabulate.tabulate(df_exito, headers='keys', tablefmt='grid'))

        #             except Exception as e:
        #                 # Si ocurre un error al actualizar SharePoint, lo muestra
        #                 print(f"Error al actualizar sharepoint: {e}")

        #     except Exception as e:
        #         # Si ocurre un error durante la ejecución de la tarea, lo muestra
        #         print(f"Ocurrió un error durante la ejecución de la tarea: {e}")
            
        # elif codigo == '3':
        #     print('\n-> Detección automática de OTs en Connecteam')

        #     try:
        #         run_interval = int(input('-> Frecuencia de ejecución [min]: '))
        #     except ValueError:
        #         print("Entrada inválida. Usando 10 minutos por defecto.")
        #         run_interval = 10

        #     schedule.every(run_interval).minutes.do(job)
        #     print(f"\nEl script de registro se ha iniciado. La tarea se ejecutará cada {run_interval} minutos.")

        #     print("[Presiona Ctrl+C para detener el script]")
        
        #     try:
        #         while True:
        #             schedule.run_pending()
        #             time.sleep(1)
        #     except KeyboardInterrupt:
        #         print("\n-> Script detenido por el usuario. ¡Hasta luego!")
            
        elif codigo == '4':
            print('Saliendo del programa...')
            break

if __name__ == "__main__":
    main()
