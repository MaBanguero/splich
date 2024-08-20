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

def log_resized_video(original_filename):
    with open(LOG_FILE, 'a') as log:
        log.write(original_filename + '\n')

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
        video_filename = os.path
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

def log_resized_video(original_filename):
    with open(LOG_FILE, 'a') as log:
        log.write(original_filename + '\n')

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
        video_filename = os.path
