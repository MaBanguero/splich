import os
import random
import boto3
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip, ImageClip
from moviepy.audio.fx.all import audio_loop
from config import Config

s3 = boto3.client('s3')

def upload_to_s3(file_path, s3_folder):
    s3_key = f"{s3_folder}/{os.path.basename(file_path)}"
    s3.upload_file(file_path, Config.S3_BUCKET_NAME, s3_key)
    os.remove(file_path)  # Elimina el archivo local después de subirlo
    return f"s3://{Config.S3_BUCKET_NAME}/{s3_key}"

def cortar_video(input_video_path, duracion_segmento):
    video = VideoFileClip(input_video_path).resize((720, 1080))
    duracion_total = int(video.duration)
    segments = []

    for start_time in range(0, duracion_total, duracion_segmento):
        end_time = min(start_time + duracion_segmento, duracion_total)
        clip = video.subclip(start_time, end_time)
        output_filename = f"segmento_{start_time}_{end_time}.mp4"
        output_path = f"/tmp/{output_filename}"  # Guardar temporalmente en el sistema de archivos local

        # Guardar el clip temporalmente
        clip.write_videofile(output_path, codec='libx264', audio_codec='aac')

        # Subir a S3 en la subcarpeta 'segments'
        s3_url = upload_to_s3(output_path, 'segments')
        segments.append(s3_url)

    return segments

def cortar_y_mezclar_video(input_video_path, duracion_segmento):
    video = VideoFileClip(input_video_path).resize((720, 1080))
    duracion_total = int(video.duration)
    clips = []

    for start_time in range(0, duracion_total, duracion_segmento):
        end_time = min(start_time + duracion_segmento, duracion_total)
        clip = video.subclip(start_time, end_time)
        clips.append(clip)

    random.shuffle(clips)
    video_final = concatenate_videoclips(clips)
    output_filename = "video_mezclado.mp4"
    output_path = f"/tmp/{output_filename}"
    video_final.write_videofile(output_path, codec='libx264', audio_codec='aac')

    # Subir a S3 en la subcarpeta 'randomized'
    return upload_to_s3(output_path, 'randomized')

def agregar_inicio_final(input_video_paths, inicio_path=None, final_path=None):
    videos_procesados = []

    inicio_clip = VideoFileClip(inicio_path).resize((720, 1080)) if inicio_path else None
    final_clip = VideoFileClip(final_path).resize((720, 1080)) if final_path else None

    for input_video_path in input_video_paths:
        video = VideoFileClip(input_video_path).resize((720, 1080))
        clips = [video]
        if inicio_clip:
            clips.insert(0, inicio_clip)
        if final_clip:
            clips.append(final_clip)
        combined_clip = concatenate_videoclips(clips)

        output_filename = f"procesado_{os.path.basename(input_video_path)}"
        output_path = f"/tmp/{output_filename}"
        combined_clip.write_videofile(output_path, codec='libx264', audio_codec='aac')

        # Subir a S3 en la subcarpeta 'processed'
        s3_url = upload_to_s3(output_path, 'processed')
        videos_procesados.append(s3_url)

    return videos_procesados

def add_logo_and_background_audio(video_path, logo_path, audio_path, logo_position=("center", "top")):
    # Cargar el video
    video = VideoFileClip(video_path).resize((720, 1080))
    
    # Cargar el logo
    logo = (ImageClip(logo_path)
            .set_duration(video.duration)
            .resize(height=50)  # Cambiar el tamaño del logo
            .set_position(logo_position)  # Posición del logo
            .set_opacity(0.5))  # Opacidad del logo

    # Cargar el audio de fondo
    background_audio = AudioFileClip(audio_path)
    
    # Repetir el audio para que coincida con la duración del video
    if background_audio.duration < video.duration:
        background_audio = audio_loop(background_audio, duration=video.duration)

    # Crear el video con el logo superpuesto
    final_video = CompositeVideoClip([video, logo])
    
    # Agregar el audio de fondo
    final_video = final_video.set_audio(background_audio)

    # Exportar el video final
    output_filename = f"final_video.mp4"
    output_path = f"/tmp/{output_filename}"
    final_video.write_videofile(output_path, codec='libx264', audio_codec='aac')

    # Subir a S3 en la subcarpeta 'processed'
    return upload_to_s3(output_path, 'processed')
