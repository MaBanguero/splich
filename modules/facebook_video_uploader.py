import boto3
import requests
import os
import logging

# Configuración del log
logging.basicConfig(filename='upload.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class FacebookVideoUploader:
    def __init__(self, app_id, page_id, page_access_token, user_access_token):
        self.s3_bucket = 'facebook-videos-bucket'
        self.s3_folder = 'reel'
        self.app_id = app_id
        self.page_id = page_id
        self.page_access_token = page_access_token
        self.user_access_token = user_access_token
        self.uploaded_videos = []  # Lista para registrar los videos subidos

        # Inicia la sesión con S3
        self.s3_client = boto3.client('s3')

    def download_videos_from_s3(self, limit=5):
        """Descarga videos de S3 hasta un límite especificado."""
        response = self.s3_client.list_objects_v2(Bucket=self.s3_bucket, Prefix=self.s3_folder)
        video_files = [content['Key'] for content in response.get('Contents', []) if content['Key'].endswith(('.mp4', '.mov'))]

        downloaded_videos = []
        for video in video_files[:limit]:
            local_filename = video.split('/')[-1]
            self.s3_client.download_file(self.s3_bucket, video, local_filename)
            downloaded_videos.append(local_filename)
            logging.info(f'Video descargado de S3: {local_filename}')

        return downloaded_videos

    def initiate_upload_session(self, file_name):
        """Inicia una sesión de subida en Facebook."""
        file_size = os.path.getsize(file_name)
        file_type = 'video/mp4'  # Ajusta esto según el tipo de archivo si es necesario

        url = f"https://graph.facebook.com/v20.0/{self.app_id}/uploads"
        params = {
            'file_name': file_name,
            'file_length': file_size,
            'file_type': file_type,
            'access_token': self.user_access_token
        }

        response = requests.post(url, params=params)
        response.raise_for_status()
        upload_session_id = response.json().get('id').replace('upload:', '')
        logging.info(f'Sesión de subida iniciada para {file_name} con ID de sesión {upload_session_id}')
        return upload_session_id

    def upload_video(self, file_name, upload_session_id):
        """Sube el video en una sesión ya iniciada."""
        url = f"https://graph.facebook.com/v20.0/upload:{upload_session_id}"
        headers = {
            "Authorization": f"OAuth {self.user_access_token}",
            "file_offset": "0"
        }

        with open(file_name, 'rb') as file_data:
            response = requests.post(url, headers=headers, data=file_data)
            response.raise_for_status()
            uploaded_file_handle = response.json().get('h')  # Extraer 'h' de la respuesta
            logging.info(f'Video {file_name} subido con éxito. Handle de archivo subido: {uploaded_file_handle}')
            return uploaded_file_handle

    def publish_video_to_facebook(self, video_title, video_description, uploaded_file_handle):
        """Publica el video en Facebook usando el identificador de archivo subido."""
        url = f"https://graph-video.facebook.com/v20.0/{self.page_id}/videos"
        files = {
            'access_token': self.page_access_token,
            'title': video_title,
            'description':  video_description,
            'fbuploader_video_file_chunk': uploaded_file_handle,
        }

        response = requests.post(url, files=files)
        print(files)
        print(response.json())
        response.raise_for_status()
        result = response.json()
        
        logging.info(f'Video publicado en Facebook con identificador: {result}')
        return result

    def publish_videos(self, limit=5):
        """Descarga, sube y publica videos en Facebook, y registra los videos subidos."""
        videos_to_upload = self.download_videos_from_s3(limit)

        for video in videos_to_upload:
            try:
                logging.info(f"Subiendo el video {video}...")
                upload_session_id = self.initiate_upload_session(video)
                uploaded_file_handle = self.upload_video(video, upload_session_id)
                video_title = "Estoy seguro de que no sabias esto"
                video_description = "Estoy seguro de que no sabias esto #fyp #virals"
                self.publish_video_to_facebook(video_title, video_description, uploaded_file_handle)
                self.uploaded_videos.append({
                    'video_name': video,
                    'uploaded_file_handle': uploaded_file_handle
                })
                logging.info(f"Video {video} subido y publicado correctamente.")
            except Exception as e:
                logging.error(f"Error al subir y publicar el video {video}: {e}")

    def get_uploaded_videos(self):
        """Retorna la lista de videos subidos."""
        return self.uploaded_videos
