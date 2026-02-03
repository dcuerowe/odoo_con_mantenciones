import requests
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from config import FORM_ID

def filter_submissions(API_key_connecteam):
    # Define la zona horaria de Chile
    chile_tz = ZoneInfo("America/Santiago")

    # Obtiene la fecha actual
    today = date(2025, 11, 12)   

    # Calcula la fecha de hace 5 días
    yesterday = today - timedelta(days=4)

    # Calcula el inicio del día (medianoche) de hace 5 días en la zona horaria de Chile
    start_of_day_chile = datetime.combine(yesterday, datetime.min.time(), tzinfo=chile_tz)
    # Convierte el inicio del día a UTC
    start_of_day_utc =  start_of_day_chile.astimezone(timezone.utc)
    # Obtiene el timestamp en segundos para el inicio del rango
    start_timestamp_ms = int(start_of_day_utc.timestamp())

    # Calcula el fin del día de mañana en la zona horaria de Chile
    end_of_day_chile = datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=chile_tz)
    # Convierte el fin del día a UTC
    end_of_day_utc = end_of_day_chile.astimezone(timezone.utc)
    # Obtiene el timestamp en segundos para el final del rango, restando 1 para incluir solo hasta el final de hoy
    end_timestamp_ms = int(end_of_day_utc.timestamp()) - 1

    # Construye la URL para la API de Connecteam con los parámetros de rango de fechas y paginación
    url = f"https://api.connecteam.com/forms/v1/forms/{FORM_ID}/form-submissions?submittingStartTimestamp={start_timestamp_ms}&submittingEndTime={end_timestamp_ms}&limit=100&offset=0"

    # Define los encabezados para la solicitud HTTP, incluyendo la API key
    headers = {
        "accept": "application/json",
        "X-API-KEY": f"{API_key_connecteam}"
    }

    # Realiza la solicitud GET a la API de Connecteam
    response = requests.get(url, headers=headers)
    # Convierte la respuesta en formato JSON
    response_json = response.json()
    # Retorna el JSON con las submissions filtradas por fecha
    return response_json

def all_submission(API_key_connecteam):
    """
    Obtiene las últimas 20 respuestas de un formulario específico desde la API de Connecteam.
    Parámetros:
        API_key_connecteam (str): Clave API necesaria para autenticar la solicitud a Connecteam.
    Funcionamiento:
        1. Define la URL del endpoint de Connecteam para obtener las respuestas del formulario.
        2. Construye los headers de la solicitud, incluyendo el API key para autenticación.
        3. Realiza una solicitud GET a la API usando la URL y los headers definidos.
        4. Convierte la respuesta recibida en formato JSON.
        5. Retorna el JSON con los datos de las respuestas del formulario.
    Retorna:
        dict: Un diccionario con la información de las respuestas del formulario obtenidas desde la API.
    """
    url = f"https://api.connecteam.com/forms/v1/forms/{FORM_ID}/form-submissions?limit=20&offset=0"

    headers = {"accept": "application/json",
            "X-API-KEY": f"{API_key_connecteam}"}

    response = requests.get(url, headers=headers)
    response_json = response.json()
    return response_json    


def form_structure(API_key_connecteam):
    """
    Obtiene la estructura de un formulario específico desde la API de Connecteam.
    Args:
        API_key_connecteam (str): Clave API necesaria para autenticar la solicitud a Connecteam.
    Returns:
        dict: Respuesta en formato JSON que contiene la estructura del formulario solicitado.
    Funcionamiento:
        1. Define la URL del formulario específico que se desea consultar.
        2. Prepara los encabezados de la solicitud, incluyendo el tipo de respuesta y la clave API.
        3. Realiza una solicitud GET a la API de Connecteam usando la URL y los encabezados definidos.
        4. Convierte la respuesta recibida en formato JSON.
        5. Retorna el JSON con la estructura del formulario.
    """
    url = f"https://api.connecteam.com/forms/v1/forms/{FORM_ID}"

    headers = {"accept": "application/json",
            "X-API-KEY": f"{API_key_connecteam}"}

    response = requests.get(url, headers=headers)
    response_json = response.json()
    return response_json

def user(API_key_connecteam, user_id):
    """
    Obtiene el nombre completo de un usuario activo desde la API de Connecteam.
    Args:
        API_key_connecteam (str): Clave API para autenticar la solicitud a Connecteam.
        user_id (int): ID del usuario cuyo nombre se desea obtener.
    Returns:
        str: Nombre completo del usuario (primer nombre y apellido).
    Funcionamiento:
        1. Construye la URL de la API con los parámetros necesarios, incluyendo el ID del usuario y el estado activo.
        2. Define los headers para la solicitud, incluyendo el API key.
        3. Realiza una solicitud GET a la API de Connecteam.
        4. Convierte la respuesta en formato JSON.
        5. Extrae el primer nombre y apellido del usuario desde la respuesta JSON.
        6. Retorna el nombre completo del usuario.
    """
    url = f"https://api.connecteam.com/users/v1/users?limit=10&offset=0&order=asc&userIds={int(user_id)}&userStatus=active"

    headers = {
        "accept": "application/json",
        "X-API-KEY": f"{API_key_connecteam}"
    }

    response = requests.get(url, headers=headers)

    response_json = response.json()

    nombre_usuario = response_json['data']['users'][0]["firstName"] + " " + response_json['data']['users'][0]["lastName"]
    return nombre_usuario
