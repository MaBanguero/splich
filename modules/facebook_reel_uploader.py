import os
import requests
import time
import threading
import boto3
from config import Config
from moviepy.editor import VideoFileClip
from moviepy.video.fx.all import resize

s3 = boto3.client('s3')

class FacebookReelsUploader:
    def __init__(self, access_token, page_id, log_file='uploaded_reels.log'):
        self.access_token = access_token
        self.page_id = page_id
        self.log_file = log_file

    def download_from_s3(self, s3_key, local_path):
        s3.download_file(Config.S3_BUCKET_NAME, s3_key, local_path)

    def resize_video(self, input_path, output_path):
        try:
            with VideoFileClip(input_path) as video:
                if video.w < 540:
                    print(f"Error: El ancho del video original ({video.w}px) es menor que el mínimo requerido (540px).")
                    return False
                
                # Redimensionar el video a 1080x1920 o usar letterbox si es necesario
                video_resized = resize(video,(1080,1920))
                
                # Guardar el video redimensionado
                video_resized.write_videofile(output_path, codec='libx264', audio_codec='aac')
                return True
        except Exception as e:
            print(f"Error al redimensionar el video: {input_path}. Detalles del error: {e}")
            return False


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
        with open(self.log_file, 'a') as log:
            log.write(video_filename + '\n')

    def get_uploaded_videos(self):
        if not os.path.exists(self.log_file):
            return set()
        with open(self.log_file, 'r') as log:
            return set(log.read().splitlines())

    def upload_videos_in_batches(self, title, description, s3_folder='segments', batch_size=5, wait_time=8*60*60):
        s3_objects = s3.list_objects_v2(Bucket=Config.S3_BUCKET_NAME, Prefix=s3_folder).get('Contents', [])
        video_files = [obj['Key'] for obj in s3_objects if obj['Key'].endswith('.mp4')]
        uploaded_videos = self.get_uploaded_videos()
        video_files = [f for f in video_files if os.path.basename(f) not in uploaded_videos]

        total_videos = len(video_files)

        for i in range(0, total_videos, batch_size):
            batch_videos = video_files[i:i+batch_size]
            for s3_key in batch_videos:
                video_filename = os.path.basename(s3_key)
                local_path = f"/tmp/{video_filename}"
                resized_path = f"/tmp/resized_{video_filename}"
                
                # Descargar el video desde S3
                self.download_from_s3(s3_key, local_path)
                
                # Redimensionar el video a 1080x1920
                if not self.resize_video(local_path, resized_path):
                    print(f"El video {video_filename} no pudo ser redimensionado correctamente.")
                    continue
                
                # Verificar que el archivo redimensionado existe
                if not os.path.exists(resized_path):
                    print(f"Error: el archivo redimensionado no se encontró en la ruta: {resized_path}")
                    continue
                
                video_id, upload_url = self.start_upload()
                if video_id and upload_url:
                    file_size = os.path.getsize(resized_path)
                    if self.upload_binary(upload_url, resized_path, file_size):
                        if self.finalize_upload(video_id, title, description):
                            print(f"Reel {video_filename} subido y publicado con éxito.")
                            self.log_uploaded_video(video_filename)
                        else:
                            print(f"Error al finalizar la publicación del Reel {video_filename}.")
                    else:
                        print(f"Error al subir el video {video_filename}.")
                else:
                    print(f"No se pudo iniciar la subida para {video_filename}.")
                
                # Eliminar los archivos locales después de la subida
                os.remove(local_path)
                os.remove(resized_path)

            if i + batch_size < total_videos:
                print(f"Esperando {wait_time/3600} horas antes de subir el siguiente lote de videos.")
                time.sleep(wait_time)  # Espera 8 horas antes de subir el siguiente lote

    def start_uploading_in_background(self, title, description, s3_folder='segments', batch_size=5, wait_time=8*60*60):
        thread = threading.Thread(target=self.upload_videos_in_batches, args=(title, description, s3_folder, batch_size, wait_time))
        thread.start()
        return thread
