import os
import random
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips
from s3_utils import upload_to_s3, download_from_s3
from subtitle_utils import add_subtitles
from transcription_utils import start_transcription_job, wait_for_job_completion, download_transcription, json_to_srt, get_bucket_region
from pysrt import open as open_srt

LOCAL_FOLDER = '/tmp'
OUTPUT_FOLDER = 'reels'
HOOKS_FOLDER = 'hooks'
FRAGMENT_DURATION = 90  # Duración de cada fragmento en segundos

def process_single_reel(video_path, video_filename, start_time, fragment_index, music_path, hooks, bucket_name):
    # Seleccionar un video "hook" aleatorio y descargarlo
    hook_video_s3_key = random.choice(hooks)
    local_hook_path = os.path.join(LOCAL_FOLDER, os.path.basename(hook_video_s3_key))
    download_from_s3(hook_video_s3_key, local_hook_path)
    hook_clip = VideoFileClip(local_hook_path)

    # Añadir música de fondo al "hook" sin reemplazar la voz
    hook_audio = hook_clip.audio
    music_clip = AudioFileClip(music_path).subclip(0, hook_clip.duration).volumex(0.25)
    combined_hook_audio = CompositeAudioClip([hook_audio, music_clip])
    hook_clip = hook_clip.set_audio(combined_hook_audio)

    # Procesar el fragmento del reel
    video_clip = VideoFileClip(video_path)
    end_time = min(start_time + FRAGMENT_DURATION, video_clip.duration)
    video_fragment = video_clip.subclip(start_time, end_time)

    # Procesar subtítulos
    transcription_job_name = f"transcription_{fragment_index}_{video_filename}"
    media_file_uri = f"s3://{bucket_name}/{video_filename}"
    start_transcription_job(bucket_name, media_file_uri, bucket_name)
    transcript_uri = wait_for_job_completion(transcription_job_name, get_bucket_region(bucket_name))
    transcript_file = download_transcription(transcript_uri, bucket_name)
    srt_file = f"{os.path.splitext(video_filename)[0]}_{fragment_index}.srt"
    json_to_srt(transcript_file, srt_file)
    
    # Aplicar subtítulos al fragmento de video
    subtitles = open_srt(srt_file)
    video_fragment = video_fragment.fl(lambda gf, t: add_subtitles(gf, t, subtitles))

    # Combinar el video "hook" con el fragmento del reel
    final_clip = concatenate_videoclips([hook_clip, video_fragment])

    # Guardar y subir el reel
    fragment_filename = f"reel_{fragment_index}_{video_filename}"
    fragment_path = os.path.join(LOCAL_FOLDER, fragment_filename)
    final_clip.write_videofile(fragment_path, codec='libx264', audio_codec='aac')

    # Subir el reel a S3
    s3_key = f"{OUTPUT_FOLDER}/{fragment_filename}"
    upload_to_s3(fragment_path, s3_key)
    
    # Limpiar archivos locales
    os.remove(fragment_path)
    os.remove(local_hook_path)
    os.remove(srt_file)

    return fragment_filename, s3_key
