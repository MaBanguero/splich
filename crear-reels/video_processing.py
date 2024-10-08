import os
import random
import uuid
import logging
import json
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips
from s3_utils import upload_to_s3, download_from_s3
from subtitle_utils import add_subtitles, open_srt
from transcription_utils import start_transcription_job, wait_for_job_completion, download_transcription, json_to_srt, get_bucket_region
from botocore.exceptions import ClientError

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LOCAL_FOLDER = '/tmp'
OUTPUT_FOLDER = 'reels'
HOOKS_FOLDER = 'hooks'
VOICES_FOLDER = 'voices'
FRAGMENT_DURATION = 83  # Duración de cada fragmento en segundos

def normalize_audio(audio_clip):
    """Normaliza el volumen del clip de audio."""
    return audio_clip.volumex(1.0)  # Ajusta el volumen a 100%

def get_voice_clip(voices, local_voice_path, voice_audio_s3_key, start_time, fragment_duration):
    """Obtiene un fragmento de voz que coincide con la duración del video."""
    download_from_s3(voice_audio_s3_key, local_voice_path)
    voice_clip = AudioFileClip(local_voice_path)
    
    # Si el start_time excede la duración, reiniciar los tiempos
    if start_time >= voice_clip.duration:
        logger.warning(f"El tiempo de inicio {start_time} excede la duración del audio {voice_clip.duration}. Tomando otro archivo de voz.")
        start_time = 0
        end_time = min(fragment_duration, voice_clip.duration)
    else:
        end_time = min(start_time + fragment_duration, voice_clip.duration)

    voice_clip = voice_clip.subclip(start_time, end_time)
    voice_clip = normalize_audio(voice_clip)

    return voice_clip, start_time, end_time

def process_single_reel(video_path, video_filename, start_time, fragment_index, music_path, hooks, voices, bucket_name):
    video_clip = VideoFileClip(video_path)
    end_time = min(start_time + FRAGMENT_DURATION, video_clip.duration)
    video_fragment = video_clip.subclip(start_time, end_time)

    # Seleccionar y descargar un archivo de voz desde la carpeta de voces
    voice_audio_s3_key = random.choice(voices)
    local_voice_path = os.path.join(LOCAL_FOLDER, os.path.basename(voice_audio_s3_key))
    
    voice_clip, voice_start_time, voice_end_time = get_voice_clip(voices, local_voice_path, voice_audio_s3_key, start_time, FRAGMENT_DURATION)

    # Asegurarse de que el nombre del archivo de salida sea correcto
    audio_s3_key = f"voice_fragment_{fragment_index}_{video_filename}.wav"
    complete_audio_path = os.path.join(LOCAL_FOLDER, audio_s3_key)

    # Escribir el archivo de audio para transcripción
    try:
        voice_clip.write_audiofile(complete_audio_path)
    except OSError as e:
        logger.error(f"Error writing audio file: {e}")
        return None, None

    # Subir el archivo de audio a S3
    upload_to_s3(complete_audio_path, audio_s3_key)
    media_file_uri = f"s3://{bucket_name}/{audio_s3_key}"

    # Generar un nombre único para el trabajo de transcripción
    transcription_job_name = f"transcription_{uuid.uuid4().hex[:8]}_{fragment_index}"

    try:
        # Iniciar el trabajo de transcripción
        logger.info(f"Iniciando trabajo de transcripción: {transcription_job_name}")
        start_transcription_job(
            bucket_name=bucket_name,
            transcription_job_name=transcription_job_name,
            media_file_uri=media_file_uri,
            output_bucket_name=bucket_name,
        )
        
        # Esperar a que el trabajo de transcripción se complete
        transcript_uri = wait_for_job_completion(transcription_job_name, get_bucket_region(bucket_name))
        logger.info(f"Trabajo de transcripción completado: {transcription_job_name}")
    except ClientError as e:
        logger.error(f"Error starting transcription job: {e}")
        raise

    # Descargar la transcripción y verificar que no esté vacía
    transcript_file = download_transcription(transcript_uri, bucket_name)
    with open(transcript_file, 'r') as f:
        transcript_data = json.load(f)
    
    if not transcript_data.get('results', {}).get('transcripts', [{}])[0].get('transcript'):
        logger.error(f"La transcripción está vacía para el trabajo {transcription_job_name}.")
        raise ValueError(f"La transcripción está vacía para el trabajo {transcription_job_name}.")
    
    # Generar el archivo SRT
    srt_file = f"{os.path.splitext(video_filename)[0]}_{fragment_index}.srt"
    json_to_srt(transcript_file, srt_file)

    # Aplicar subtítulos al fragmento de video
    subtitles = open_srt(srt_file)
    video_fragment = video_fragment.fl(lambda gf, t: add_subtitles(gf, t, subtitles))

    # Descargar y seleccionar un video "hook" aleatorio
    hook_video_s3_key = random.choice(hooks)
    local_hook_path = os.path.join(LOCAL_FOLDER, os.path.basename(hook_video_s3_key))
    download_from_s3(hook_video_s3_key, local_hook_path)
    hook_clip = VideoFileClip(local_hook_path)

    # Añadir música de fondo al "hook" sin reemplazar la voz
    hook_audio = hook_clip.audio
    music_clip = AudioFileClip(music_path).subclip(0, hook_clip.duration).volumex(0.25)

    # Crear una versión del hook con música de fondo
    combined_hook_audio = CompositeAudioClip([hook_audio, music_clip])
    hook_clip = hook_clip.set_audio(combined_hook_audio)

    # Crear una versión del fragmento con voz y música de fondo
    fragment_audio = CompositeAudioClip([voice_clip, music_clip.subclip(0, video_fragment.duration)])
    video_fragment = video_fragment.set_audio(fragment_audio)

    # Combinar el hook y el fragmento
    final_clip = concatenate_videoclips([hook_clip, video_fragment])

    # Guardar y subir el reel final
    fragment_filename = f"reel_{fragment_index}_{video_filename}"
    fragment_path = os.path.join(LOCAL_FOLDER, fragment_filename)
    final_clip.write_videofile(fragment_path, codec='libx264', audio_codec='aac')

    # Subir el reel a S3
    reel_s3_key = f"{OUTPUT_FOLDER}/{fragment_filename}"
    upload_to_s3(fragment_path, reel_s3_key)
    
    # Limpiar archivos locales
    os.remove(fragment_path)
    os.remove(local_hook_path)
    os.remove(srt_file)
    os.remove(local_voice_path)

    return fragment_filename, reel_s3_key
