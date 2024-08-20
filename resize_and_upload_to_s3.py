import os
import boto3
from moviepy.editor import VideoFileClip
from config import Config
from moviepy.video.fx.all import resize

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
            
            # Redimensionar el video a 1080x1920 o usar letterbox si es necesario
            if video.h / video.w >= 1920 / 1080:
                video_resized = resize(video, height=1920)
            else:
                video_resized = resize(video, width=1080)
            
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

def process_and_upload_videos_from_s3(s3_input_folder='segments', s3_output_folder='resized', local_folder='/tmp'):
    resized_videos = get_resized_videos()
    s3_objects = s3.list_objects_v2(Bucket=Config.S3_BUCKET_NAME, Prefix=s3_input_folder).get('Contents', [])
    video_files = [obj['Key'] for obj in s3_objects if obj['Key'].endswith('.mp4')]
    
    for s3_key in video_files:
        video_filename = os.path.basename(s3_key)
        
        # Verificar si el video ya ha sido redimensionado usando el nombre del archivo original
        if video_filename in resized_videos:
            print(f"El video {video_filename} ya ha sido redimensionado anteriormente. Saltando...")
            continue
        
        local_input_path = os.path.join(local_folder, video_filename)
        local_output_path = os.path.join(local_folder, video_filename)
        resized_s3_key = f"{s3_output_folder}/{video_filename}"
        
        # Descargar el video desde S3
        try:
            download_from_s3(s3_key, local_input_path)
        except Exception as e:
            print(f"Error al descargar el video {video_filename} desde S3: {e}")
            continue
        
        # Redimensionar el video
        if resize_video(local_input_path, local_output_path):
            try:
                # Subir el video redimensionado a S3 con el nombre original
                upload_to_s3(local_output_path, resized_s3_key)
                print(f"Video {video_filename} redimensionado y subido a S3 como {resized_s3_key}.")
                
                # Registrar el video original como redimensionado
                log_resized_video(video_filename)
            except Exception as e:
                print(f"Error al subir el video redimensionado {video_filename} a S3: {e}")
        else:
            print(f"El video {video_filename} no pudo ser redimensionado.")
        
        # Eliminar los archivos locales después de la redimensión
        try:
            os.remove(local_input_path)
            os.remove(local_output_path)
        except Exception as e:
            print(f"Error al eliminar los archivos locales para {video_filename}: {e}")

if __name__ == "__main__":
    process_and_upload_videos_from_s3()
