import os
from dotenv import load_dotenv
import certifi

# Load environment variables
load_dotenv()

# SSL Cert fix
os.environ['SSL_CERT_FILE'] = certifi.where()

# SharePoint Configuration
SHAREPOINT_USER = os.getenv('sharepoint_user')
SHAREPOINT_PASSWORD = os.getenv('sharepoint_password')
SHAREPOINT_SITE = os.getenv('sharepoint_url_site')
SHAREPOINT_NAME_SITE = os.getenv('sharepoint_site_name')
SHAREPOINT_DOC_LIBRARY = os.getenv('sharepoint_doc_library')

# Connecteam Configuration
CONNECTEAM_API_KEY = os.getenv('CONNECTEAM_API_KEY')
FORM_ID = "12914411" # Hardcoded in original code

#Odoo Configuration
ODOO_URL = os.getenv('URL_Odoo')
ODOO_DB = os.getenv('DB_Odoo')
ODOO_USER = os.getenv('USER_Odoo')
ODOO_PASSWORD = os.getenv('ODOO_API_KEY')


# ODOO_URL = os.getenv('URL_TEST')
# ODOO_DB = os.getenv('DB_TEST')
# ODOO_USER = os.getenv('USER_TEST')
# ODOO_PASSWORD = os.getenv('ODOO_API_KEY')





# URLs
LOGO_URL = "https://we-techs-static-bucket.s3.amazonaws.com/static/images/logo-middle.png"
EXCEL_URL = 'https://graph.microsoft.com/v1.0/drives/b!dx9RXh45RU6gEd39TWLgKItDBbzJweRPoWAkjonKJ4GcIDolNOD0TI7SvyLL7Hda/root:/04.%20Instalación%20y%20Mantenimiento/Trazabilidad%20de%20mantenciones%20y%20calibraciones/Captura.xlsx:/content'
SHAREPOINT_UPLOAD_BASE_URL = 'https://graph.microsoft.com/v1.0/drives/b!dx9RXh45RU6gEd39TWLgKItDBbzJweRPoWAkjonKJ4GcIDolNOD0TI7SvyLL7Hda/root:/04. Instalación y Mantenimiento/Trazabilidad de mantenciones y calibraciones/Informes de mantención'
SHAREPOINT_UPLOAD_INSTALL_BASE_URL = 'https://graph.microsoft.com/v1.0/drives/b!dx9RXh45RU6gEd39TWLgKItDBbzJweRPoWAkjonKJ4GcIDolNOD0TI7SvyLL7Hda/root:/04. Instalación y Mantenimiento/Trazabilidad de mantenciones y calibraciones/Informes de instalación'

# Other constants
RUN_INTERVAL_MINUTES = 0 # Will be set by user input or default
