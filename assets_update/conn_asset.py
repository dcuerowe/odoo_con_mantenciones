import requests
import os
import json
import traceback

#Incluir el un ciclo for dentro de las funciones para que se actulice tambien el fomrulario de contrastación

# 12052552 Entrega de proyectos


def add_new_options(API_KEY, assets_name):

    id_question = ["9d7a30fa-d3ee-c639-7b6f-60be1103c7cc","9d7a30fa-d3ee-c639-7b6f-60be1103c7cc", "da9ff9dd-2773-824a-fbe3-70d5fa33a8fd","e9693a06-d584-29e9-cf4a-07ffbe32f506"]
                   

    for id in id_question:

        url = f"https://api.connecteam.com/forms/v1/forms/15540738/questions/{id}"

        data = []
        for name in assets_name:
            data.append({ "value": name })

        payload = { "dropdownOptions": data }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "X-API-KEY": API_KEY
        }

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            print(f"Opciones agregadas exitosamente en Connecteam: ")
            for choice in assets_name:
                print(f"   - {choice}")
