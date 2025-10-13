import requests
import os
import json
import traceback


def add_new_options(API_KEY, assets_name):

    id_question = ["9d7a30fa-d3ee-c639-7b6f-60be1103c7cc", "7d421fe8-92c8-ddd0-75f2-23ecad62aff1", "5c4c3d6a-933d-c89d-89c1-21b4e0034c23", 
                   "f1de4866-466f-58b9-2b65-d8694d6c71f7", "2b81c480-30a1-25a3-a65d-507f9ba0f441", "a00e9070-96de-15cc-12fd-b90b305f77ff"]

    for id in id_question:

        url = f"https://api.connecteam.com/forms/v1/forms/12914411/questions/{id}"

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
        