import xmlrpc.client
import pandas as pd
import os
import re
import ssl


def new_asset(assets,  url, db, username, password):
    
    #Inicio de sesión
    try: 
        common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
        uid = common.authenticate(db, username, password, {})
    except Exception as e:
        print(f"Error en el inicio de sesión desde la API: {e}")
        
    #Inicialización del endpoint
    try:
        models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
    except Exception as e:
        print(f"Error en la inicialización del endpoint: {e}")


    for asset in assets:
        try:
            asset_data = {
                'x_name': asset[0],
                'x_studio_asset_id_1': asset[1],
                'x_studio_char_field_M8G1K': asset[2],
                'x_studio_ubicacin' : f'https://www.google.com/maps/place/{asset[2]}'
                
            }

            asset_id = models.execute_kw(db, uid, password, 'x_maintenance_location', 'create', [asset_data])
            print(f'Creado en Odoo: {asset[0]}')


        except Exception as e:
            print(f"Error en la creación de los datos del activo: {e}")


