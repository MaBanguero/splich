import os
import requests
import boto3

class FacebookReelsUploader:
    def __init__(self, page_id, access_token, log_file='uploaded_reels.log', bucket_name='facebook-videos-bucket', s3_folder='reel'):
        self.page_id = page_id
        self.access_token = access_token
        self.log_file = log_file
        self.bucket_name = bucket_name
        self.s3_folder = s3_folder
        self.s3_client = boto3.client('s3')

    def start_upload(self):
        upload_start_url = f"https://graph.facebook.com/v20.0/{self.page_id}/video_reels"
        data = {
            'upload_phase': 'start',
            'access_token': self.access_token
        }

        try:
            response = requests.post(upload_start_url, data=data)
            response.raise_for_status()
            initiate_upload_response = response.json()
            return initiate_upload_response.get('video_id'), initiate_upload_response.get('upload_url')
        except requests.exceptions.RequestException as e:
            print(f"Error initiating upload for FB Reels: {upload_start_url}, {e}")
            return None, None

    def upload_binary(self, upload_url, video_path, file_size):
        headers = {
            'Authorization': f'OAuth {self.access_token}',
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

    def finalize_upload(self, video_id, title, description):
        base_publish_reels_uri = (
            f"https://graph.facebook.com/{self.page_id}/video_reels?"
            f"upload_phase=finish&video_id={video_id}&title={title}"
            f"&description={description}&video_state=PUBLISHED&access_token={self.access_token}"
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

    def download_videos_from_s3(self, local_folder='/tmp'):
        s3_objects = self.s3_client.list_objects_v2(Bucket=self.bucket_name, Prefix=self.s3_folder).get('Contents', [])
        video_files = [obj['Key'] for obj in s3_objects if obj['Key'].endswith('.mp4')]
        uploaded_videos = self.get_uploaded_videos()

        for s3_key in video_files:
            video_filename = os.path.basename(s3_key)
            if video_filename in uploaded_videos:
                print(f"El video {video_filename} ya ha sido subido anteriormente. Saltando...")
                continue

            local_path = os.path.join(local_folder, video_filename)
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            yield local_path, video_filename

    def upload_videos(self, title, description, local_folder='/tmp', batch_size=5, max_videos=30):
        video_generator = self.download_videos_from_s3(local_folder)
        video_files = list(video_generator)[:max_videos]  # Limitar a un máximo de 30 videos
        total_videos = len(video_files)

        for i in range(0, total_videos, batch_size):
            batch_videos = video_files[i:i + batch_size]

            for video_path, video_filename in batch_videos:
                if not os.path.exists(video_path):
                    print(f"Error: el archivo {video_filename} no existe en la ruta {video_path}. Saltando...")
                    continue
                
                video_id, upload_url = self.start_upload()
                if video_id and upload_url:
                    file_size = os.path.getsize(video_path)
                    if self.upload_binary(upload_url, video_path, file_size):
                        if self.finalize_upload(video_id, title, description):
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
