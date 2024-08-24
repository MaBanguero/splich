import os
import boto3
from moviepy.editor import VideoFileClip, AudioFileClip
from pydub import AudioSegment

s3 = boto3.client('s3')
BUCKET_NAME = 'facebook-videos-bucket'
VIDEO_FOLDER = 'video-to-mix'
AUDIO_FOLDER = 'voices'
LOCAL_FOLDER = '/tmp'
OUTPUT_FOLDER = 'reels'
FRAGMENT_DURATION = 90  # Duración en segundos para cada fragmento
FRAGMENT_LOG_FILE = 'processed_fragments.log'  # Archivo para llevar el registro

def download_from_s3(s3_key, local_path):
    s3.download_file(BUCKET_NAME, s3_key, local_path)

def upload_to_s3(local_path, s3_key):
    s3.upload_file(local_path, BUCKET_NAME, s3_key)

def repeat_audio_to_fit_video(audio_clip, video_duration):
    audio_duration = audio_clip.duration
    if audio_duration >= video_duration:
        return audio_clip.subclip(0, video_duration)
    else:
        # Repetir el audio usando pydub hasta que sea igual o mayor que la duración del video
        audio = AudioSegment.from_file(audio_clip.filename)
        repetitions = int(video_duration // audio_duration) + 1
        extended_audio = audio * repetitions
        extended_audio = extended_audio[:int(video_duration * 1000)]  # Cortar al tamaño exacto
        extended_audio.export(audio_clip.filename, format="wav")
        return AudioFileClip(audio_clip.filename)

def load_processed_fragments():
    processed_fragments = {}
    if not os.path.exists(FRAGMENT_LOG_FILE):
        return processed_fragments
    with open(FRAGMENT_LOG_FILE, 'r') as log_file:
        for line in log_file:
            parts = line.strip().split(',')
            if len(parts) < 3:
                print(f"Línea malformada en el archivo de log: {line}")
                continue
            video_filename = parts[0]
            last_fragment = int(parts[1])
            complete = parts[2].strip() == 'complete'
            processed_fragments[video_filename] = {
                'last_fragment': last_fragment,
                'complete': complete
            }
    return processed_fragments

def save_processed_fragment(video_filename, fragment_index, complete=False):
    with open(FRAGMENT_LOG_FILE, 'a') as log_file:
        status = 'complete' if complete else 'incomplete'
        log_file.write(f"{video_filename},{fragment_index},{status}\n")

def process_video_and_audio():
    s3_video_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=VIDEO_FOLDER).get('Contents', [])
    s3_audio_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=AUDIO_FOLDER).get('Contents', [])

    video_files = [obj['Key'] for obj in s3_video_objects if obj['Key'].endswith('.mp4')]
    audio_files = [obj['Key'] for obj in s3_audio_objects if obj['Key'].endswith('.mp3') or obj['Key'].endswith('.wav')]

    if not video_files or not audio_files:
        print("No se encontraron archivos de video o audio.")
        return

    # Cargar fragmentos procesados previamente
    processed_fragments = load_processed_fragments()

    for video_s3_key in video_files:
        video_filename = os.path.basename(video_s3_key)
        audio_s3_key = audio_files[0]  # Usar el primer archivo de audio para todos los videos
        audio_filename = os.path.basename(audio_s3_key)

        if video_filename in processed_fragments and processed_fragments[video_filename]['complete']:
            print(f"El video {video_filename} ya ha sido procesado completamente. Saltando...")
            continue

        local_video_path = os.path.join(LOCAL_FOLDER, video_filename)
        local_audio_path = os.path.join(LOCAL_FOLDER, audio_filename)

        # Verificar si el video ya existe en /tmp para evitar la descarga desde S3
        if not os.path.exists(local_video_path):
            print(f"Descargando {video_filename} desde S3...")
            download_from_s3(video_s3_key, local_video_path)
        else:
            print(f"El video {video_filename} ya existe en {LOCAL_FOLDER}, omitiendo la descarga desde S3.")

        # Verificar si el audio ya existe en /tmp para evitar la descarga desde S3
        if not os.path.exists(local_audio_path):
            print(f"Descargando {audio_filename} desde S3...")
            download_from_s3(audio_s3_key, local_audio_path)
        else:
            print(f"El audio {audio_filename} ya existe en {LOCAL_FOLDER}, omitiendo la descarga desde S3.")

        print(f"Procesando video: {video_filename}")
        print(f"Fragmentos procesados hasta ahora: {processed_fragments}")

        last_processed_fragment = processed_fragments.get(video_filename, {}).get('last_fragment', 0)
        
        # Debugging information
        print(f"Último fragmento procesado para {video_filename}: {last_processed_fragment}")

        # Procesar video en fragmentos más pequeños
        video_clip = VideoFileClip(local_video_path)
        audio_clip = AudioFileClip(local_audio_path)

        # Dividir y procesar video en fragmentos de 90 segundos
        start_time = last_processed_fragment * FRAGMENT_DURATION
        fragment_index = last_processed_fragment + 1

        while start_time < video_clip.duration:
            end_time = min(start_time + FRAGMENT_DURATION, video_clip.duration)
            video_fragment = video_clip.subclip(start_time, end_time)
            audio_fragment = repeat_audio_to_fit_video(audio_clip.subclip(start_time, end_time), video_fragment.duration)

            final_video_fragment = video_fragment.set_audio(audio_fragment)

            fragment_filename = f"fragment_{fragment_index}_{video_filename}"
            fragment_path = os.path.join(LOCAL_FOLDER, fragment_filename)
            final_video_fragment.write_videofile(fragment_path, codec='libx264', audio_codec='aac')

            upload_to_s3(fragment_path, f"{OUTPUT_FOLDER}/{fragment_filename}")
            os.remove(fragment_path)  # Limpiar archivos locales

            # Guardar el fragmento procesado
            save_processed_fragment(video_filename, fragment_index)

            start_time += FRAGMENT_DURATION
            fragment_index += 1

        # Marcar el video como completamente procesado
        save_processed_fragment(video_filename, fragment_index - 1, complete=True)

        # Limpiar archivos locales
        os.remove(local_video_path)
        os.remove(local_audio_path)

if __name__ == "__main__":
    process_video_and_audio()
