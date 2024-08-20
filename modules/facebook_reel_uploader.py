import os
import requests
import threading

class FacebookReelsUploader:
    def __init__(self, page_id, log_file='uploaded_reels.log'):
        self.page_id = page_id
        self.log_file = log_file

    def start_upload(self, access_token):
        upload_start_url = f"https://graph.facebook.com/v20.0/{self.page_id}/video_reels"
        data = {
            'upload_phase': 'start',
            'access_token': access_token
        }

        try:
            response = requests.post(upload_start_url, data=data)
            response.raise_for_status()
            initiate_upload_response = response.json()
            return initiate_upload_response.get('video_id'), initiate_upload_response.get('upload_url')
        except requests.exceptions.RequestException as e:
            print(f"Error initiating upload for FB Reels: {upload_start_url}, {e}")
            return None, None

    def upload_binary(self, upload_url, video_path, file_size, access_token):
        headers = {
            'Authorization': f'OAuth {access_token}',
            'offset': '0',
            'file_size': str(file_size)
        }

        with open(video_path, 'rb') as video_file:
            try:
                response = requests.post(upload_url, headers=headers, data=video_file)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Error uploading binary for Facebook Reels: {upload_url}, {e}")
                return None

    def finalize_upload(self, video_id, title, description, access_token):
        base_publish_reels_uri = (
            f"https://graph.facebook.com/{self.page_id}/video_reels?"
            f"upload_phase=finish&video_id={video_id}&title={title}"
            f"&description={description}&video_state=PUBLISHED&access_token={access_token}"
        )
        try:
            response = requests.post(base_publish_reels_uri)
            response.raise_for_status()
            print(response.json())
            return response.json().get('success')
        except requests.exceptions.RequestException as e:
            print(f"Error publishing for Facebook Reels: {base_publish_reels_uri}, {e}")
            return None

    def log_uploaded_video(self, video_filename):
        try:
            with open(self.log_file, 'a') as log:
                log.write(video_filename + '\n')
        except IOError as e:
            print(f"Error al escribir en el archivo de log: {e}")

    def get_uploaded_videos(self):
        if not os.path.exists(self.log_file):
            return set()
        try:
            with open(self.log_file, 'r') as log:
                return set(log.read().splitlines())
        except IOError as e:
            print(f"Error al leer el archivo de log: {e}")
            return set()

    def upload_videos(self, title, description, video_folder='/tmp', batch_size=5):
        all_files = [f for f in os.listdir(video_folder) if f.startswith('redimensionado-') and f.endswith('.mp4')]
        uploaded_videos = self.get_uploaded_videos()
        video_files = [f for f in all_files if f not in uploaded_videos]

        total_videos = len(video_files)
        
        for i in range(0, total_videos, batch_size):
            batch_videos = video_files[i:i+batch_size]

            # Solicitar el access_token una vez por cada lote de 5 videos
            access_token = input(f"Introduce el access_token para subir este lote de {min(batch_size, len(batch_videos))} videos: ")

            for video_filename in batch_videos:
                video_path = os.path.join(video_folder, video_filename)

                # Verificación de existencia del archivo antes de intentar subirlo
                if not os.path.exists(video_path):
                    print(f"Error: el archivo {video_filename} no existe en la ruta {video_path}. Saltando...")
                    continue
                
                video_id, upload_url = self.start_upload(access_token)
                if video_id and upload_url:
                    file_size = os.path.getsize(video_path)
                    if self.upload_binary(upload_url, video_path, file_size, access_token):
                        if self.finalize_upload(video_id, title, description, access_token):
                            print(f"Reel {video_filename} subido y publicado con éxito.")
                            self.log_uploaded_video(video_filename)
                            
                            # Opción para eliminar el archivo local después de la subida
                            try:
                                os.remove(video_path)
                            except OSError as e:
                                print(f"Error al eliminar el archivo {video_filename}: {e}")
                        else:
                            print(f"Error al finalizar la publicación del Reel {video_filename}.")
                    else:
                        print(f"Error al subir el video {video_filename}.")
                else:
                    print(f"No se pudo iniciar la subida para {video_filename}.")

    def start_uploading_in_background(self, title, description, video_folder='/tmp', batch_size=5):
        thread = threading.Thread(target=self.upload_videos, args=(title, description, video_folder, batch_size))
        thread.start()
        return thread
