import xmlrpc.client
import pandas as pd
from dotenv import load_dotenv
import os
import re
import ssl
import certifi

from conn_asset import add_new_options  
from odoo_asset import new_asset
from ticket_asset import add_choices_to_field

load_dotenv.load_dotenv()

#Credenciales Freshdesk
api_key_fresh = os.getenv('Fresh_API_KEY')
domain_fresh = os.getenv('Fresh_domain')

#credenciales Odoo
url = os.getenv('URL_Odoo')
db = os.getenv('DB_Odoo')
username = os.getenv('USER_Odoo')
password = os.getenv('ODOO_API_KEY')

#Credenciales Connecteam
API_KEY = os.getenv('CONNECTEAM_API_KEY')

#SSL
os.environ['SSL_CERT_FILE'] = certifi.where()

asset_list = []
assets_name = []
i = 1
while True:
    asset = []
    name = input(f'Nombre asset {i}: ')
    asset_id = input(f'ID asset {i}: ')
    coordenadas = input(f'Coordenadas (latitud, longitud) {i}: ')
    i += 1

    asset.append(name)
    assets_name.append(name)
    asset.append(asset_id)
    asset.append(coordenadas)
    asset_list.append(asset)

    print('-------------------------------------------')
    continuar = input('¿Desea agregar otro asset? (s/n): ')
    if continuar.lower() != 's':
        break


#Actualizando Freshdesk
add_choices_to_field(
    domain=domain_fresh,
    api_key=api_key_fresh,
    field_id=151001231887,
    new_points=assets_name)

#Actualizando Odoo
new_asset(asset_list,
        url,
        db,
        username,
        password)

#Actualizando Connecteam
add_new_options(API_KEY,
    assets_name)
    




