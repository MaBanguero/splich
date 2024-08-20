import os
import boto3
from datetime import datetime
from moviepy.editor import VideoFileClip
from moviepy.video.fx.all import resize
from config import Config

s3 = boto3.client('s3')
LOG_FILE = 'resized_videos.log'

def download_from_s3(s3_key, local_path):
    s3.download_file(Config.S3_BUCKET_NAME, s3_key, local_path)

def upload_to_s3(local_path, s3_key):
    s3.upload_file(local_path, Config.S3_BUCKET_NAME, s3_key)

def resize_video(input_path, output_path):
    try:
        with VideoFileClip(input_path) as video:
            if video.w < 540:
                print(f"Error: El ancho del video original ({video.w}px) es menor que el mínimo requerido (540px).")
                return False
                
            # Aplicar letterbox si es necesario para mantener la proporción 9:16
            video_resized = video_resized.resize((1080, 1920))
            
            # Guardar el video redimensionado
            video_resized.write_videofile(output_path, codec='libx264', audio_codec='aac')
            return True
    except Exception as e:
        print(f"Error al redimensionar el video: {input_path}. Detalles del error: {e}")
        return False

def log_resized_video(video_filename):
    with open(LOG_FILE, 'a') as log:
        log.write(video_filename + '\n')

def get_resized_videos():
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, 'r') as log:
        return set(log.read().splitlines())

def process_and_upload_videos_from_s3(s3_folder='segments', output_folder='/tmp'):
    resized_videos = get_resized_videos()
    s3_objects = s3.list_objects_v2(Bucket=Config.S3_BUCKET_NAME, Prefix=s3_folder).get('Contents', [])
    video_files = [obj['Key'] for obj in s3_objects if obj['Key'].endswith('.mp4')]
    
    for s3_key in video_files:
        video_filename = os.path.basename(s3_key)
        
        # Verificar si el video ya ha sido redimensionado
        if video_filename in resized_videos:
            print(f"El video {video_filename} ya ha sido redimensionado anteriormente. Saltando...")
            continue
        
        local_path = os.path.join(output_folder, video_filename)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        resized_filename = f"redimensionado-{timestamp}-{video_filename}"
        resized_path = os.path.join(output_folder, resized_filename)
        resized_s3_key = f"{s3_folder}/redimensionados/{resized_filename}"
        
        # Descargar el video desde S3
        download_from_s3(s3_key, local_path)
        
        # Redimensionar el video
        if resize_video(local_path, resized_path):
            # Subir el video redimensionado a S3
            upload_to_s3(resized_path, resized_s3_key)
            print(f"Video {video_filename} redimensionado y subido a S3 como {resized_s3_key}.")
            
            # Registrar el video como redimensionado
            log_resized_video(video_filename)
        else:
            print(f"El video {video_filename} no pudo ser redimensionado.")
        
        # Eliminar los archivos locales después de la redimensión
        os.remove(local_path)
        os.remove(resized_path)

if __name__ == "__main__":
    process_and_upload_videos_from_s3()
