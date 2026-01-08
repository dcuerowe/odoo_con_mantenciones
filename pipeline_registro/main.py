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
        ordered_responses_2 = ordenar_respuestas(form_structure(CONNECTEAM_API_KEY), all_submission(CONNECTEAM_API_KEY))
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


if __name__ == "__main__":
    job()
