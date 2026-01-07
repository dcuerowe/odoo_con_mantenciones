import time
from conn_sharepoint import get_auth_token, get_file_from_sharepoint, upload_file_to_sharepoint

class Sharepoint:

    def __init__(self):
        self.token = get_auth_token()

    def download_file(self, file_name, folder_name = ''):
        """
        Descarga un archivo desde una carpeta específica de SharePoint.

        Args:
            file_name (str): Nombre del archivo a descargar.
            folder_name (str): Nombre de la carpeta dentro de la biblioteca de documentos.

        Returns:
            bytes: El contenido del archivo en formato binario si la descarga es exitosa.
            None: Si ocurre un error durante la descarga.
        """

        try:
            # Obtiene la referencia al archivo usando la URL relativa
            file = get_file_from_sharepoint(file_name, self.token)
            # Devuelve el contenido binario del archivo
            return file.content
        
        except Exception as e:
            # Si ocurre un error, lo muestra y devuelve None
            print(f"Error al descargar el archivo {file_name} de SharePoint: {e}")
            return None
    
    def upload_file(self, file_name, content_stream, content_type = None, folder_name = ''):
        """Sube un archivo binario a una carpeta de SharePoint."""
        
        try:
            # Obtiene la referencia de la carpeta destino en SharePoint
        
            content_stream.seek(0)  # Asegura que el stream esté al inicio
            # Sube el archivo usando el contenido del stream
            target_file = upload_file_to_sharepoint(file_name, self.token, content_stream.getvalue(), content_type)

            # Ejecuta la consulta para completar la subida
            

            print(f"\n-> Archivo '{file_name}' subido con éxito en el intento 1")
            return True  # Retorna True si la subida fue exitosa
        
        except Exception as e:
            error_str = str(e)
            # Verifica si el error es por archivo bloqueado en SharePoint
            if "SPFileLockException" in error_str or "423 Client Error: Locked" in error_str:
                print(f"El archivo '{file_name}' está bloqueado. Reintentando en 5 segundos...")
                time.sleep(5)
            else:
                # Si es otro tipo de error, lo reporta y termina
                print(f"Error al subir el archivo a SharePoint: {error_str}")
                return None  # Retorna None en caso de error inesperado
