import requests
import os
import json
import traceback



def add_choices_to_field(domain: str, api_key: str, field_id: int, new_points: list):
    """
    Agrega nuevas opciones a un ticket field de tipo multichoice/dropdown en Freshdesk.

    :param domain: Dominio de Freshdesk (ej: "tudominio.freshdesk.com")
    :param api_key: API key de Freshdesk
    :param field_id: ID del campo de ticket (ej: 151001231887)
    :param new_points: Lista de strings con las nuevas opciones (ej: ["Opción 1", "Opción 2"])
    """

    password = "X"  # Freshdesk requiere este placeholder
    url = f"https://{domain}.freshdesk.com/api/v2/admin/ticket_fields/{field_id}"

    print(domain)

    # 1. Obtener las opciones actuales
    response = requests.get(url, auth=(api_key, password))
    if response.status_code != 200:
        raise Exception(f"Error al obtener el field: {response.status_code} {response.text}")

    field_data = response.json()
    current_choices = field_data.get("choices", [])

    # 2. Transformar los strings en diccionarios {label: x, value: x}
    start_position = len(current_choices) + 1
    formatted_new_choices = [
        {"label": point, "value": point, "position": start_position + i}
        for i, point in enumerate(new_points)
    ]

    # 3. Combinar con las existentes
    updated_choices = field_data.get("choices", []) + formatted_new_choices

    # 4. Hacer PUT para actualizar el field
    payload = {"choices": updated_choices}
    update_response = requests.put(url, auth=(api_key, password), json=payload)

    if update_response.status_code == 200:
        print(f"Opciones agregadas exitosamente en fresh desk: ")
        for choice in new_points:
            print(f"   - {choice}")
        return update_response.json()
    else:
        raise Exception(f"Error al actualizar el field: {update_response.status_code} {update_response.text}")




