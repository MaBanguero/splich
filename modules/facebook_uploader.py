import os
import requests
import time
import threading

class FacebookUploader:
    def __init__(self, access_token, page_id, log_file='uploaded_videos.log'):
        self.access_token = access_token
        self.page_id = page_id
        self.api_url = f"https://graph.facebook.com/v16.0/{self.page_id}/videos"
        self.log_file = log_file

    def upload_video(self, video_filename, title, description, segments_folder='static/uploads/segments'):
        video_path = os.path.join(segments_folder, video_filename)

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"El archivo de video {video_path} no se encontró.")

        # Preparar los datos para la solicitud
        files = {
            'file': open(video_path, 'rb')
        }
        params = {
            'access_token': self.access_token,
            'title': title,
            'description': description,
        }

        # Realizar la solicitud POST para subir el video
        response = requests.post(self.api_url, files=files, data=params)
        files['file'].close()

        # Verificar si la subida fue exitosa
        if response.status_code == 200:
            self.log_uploaded_video(video_filename)
            return {"success": True, "response": response.json()}
        else:
            return {"success": False, "status_code": response.status_code, "response": response.json()}

    def upload_videos_in_batches(self, title, description, segments_folder='static/uploads/segments', batch_size=5, wait_time=5*60*60):
        video_files = [f for f in os.listdir(segments_folder) if f.endswith('.mp4')]
        uploaded_videos = self.get_uploaded_videos()

        # Filtrar videos que ya han sido subidos
        video_files = [f for f in video_files if f not in uploaded_videos]

        total_videos = len(video_files)
        
        for i in range(0, total_videos, batch_size):
            batch_videos = video_files[i:i+batch_size]
            for video_filename in batch_videos:
                result = self.upload_video(video_filename, title, description, segments_folder)
                if result['success']:
                    print(f"Video {video_filename} subido con éxito.")
                else:
                    print(f"Error al subir el video {video_filename}: {result['status_code']}")
                    print("Response:", result['response'])

            if i + batch_size < total_videos:
                print(f"Esperando {wait_time/3600} horas antes de subir el siguiente lote de videos.")
                time.sleep(wait_time)  # Espera 5 horas antes de subir el siguiente lote

    def start_uploading_in_background(self, title, description, segments_folder='static/uploads/segments', batch_size=5, wait_time=5*60*60):
        thread = threading.Thread(target=self.upload_videos_in_batches, args=(title, description, segments_folder, batch_size, wait_time))
        thread.start()
        return thread

    def log_uploaded_video(self, video_filename):
        """Registra un video como subido escribiéndolo en el archivo de registro."""
        with open(self.log_file, 'a') as log:
            log.write(video_filename + '\n')

    def get_uploaded_videos(self):
        """Devuelve un conjunto de los nombres de videos que ya han sido subidos."""
        if not os.path.exists(self.log_file):
            return set()

        with open(self.log_file, 'r') as log:
            uploaded_videos = log.read().splitlines()
        return set(uploaded_videos)
