import os
import msal
from dotenv import load_dotenv
import requests


load_dotenv()
 
authority_link = f'https://login.microsoftonline.com/{os.environ["MS_TENANT"]}'
 
def get_auth_token():
    """
    Gets an authentication token from Microsoft Graph API.
    """



    app = msal.ConfidentialClientApplication(
        client_id=os.environ["MS_CLIENT_ID"],
        client_credential=os.environ["MS_CLIENT_SECRET"],
        authority=authority_link
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    return result['access_token']


def get_file_from_sharepoint(url, token):
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    return response


def upload_file_to_sharepoint(url, token, file_content, content_type = 'vnd.openxmlformats-officedocument.spreadsheetml.sheet'):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"application/{content_type}"
    }
    response = requests.put(url, headers=headers, data=file_content)
    return response