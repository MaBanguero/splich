import os
import random
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips
from s3_utils import upload_to_s3, download_from_s3
from subtitle_utils import add_subtitles

LOCAL_FOLDER = '/tmp'
OUTPUT_FOLDER = 'reels'
HOOKS_FOLDER = 'hooks'
FRAGMENT_DURATION = 90  # Duración de cada fragmento en segundos

def process_single_reel(video_path, video_filename, start_time, fragment_index, audio_path, music_path, subtitles, hooks):
    video_clip = VideoFileClip(video_path)
    end_time = min(start_time + FRAGMENT_DURATION, video_clip.duration)
    video_fragment = video_clip.subclip(start_time, end_time)

    # Descargar y seleccionar un video "hook" aleatorio
    hook_video_s3_key = random.choice(hooks)
    local_hook_path = os.path.join(LOCAL_FOLDER, os.path.basename(hook_video_s3_key))
    download_from_s3(hook_video_s3_key, local_hook_path)
    hook_clip = VideoFileClip(local_hook_path)

    # Añadir música al video "hook"
    music_clip = AudioFileClip(music_path).subclip(0, hook_clip.duration).volumex(0.25)
    hook_clip = hook_clip.set_audio(music_clip)

    # Cargar los clips de audio y música para el fragmento
    voice_clip = AudioFileClip(audio_path).subclip(start_time, end_time)
    music_clip = AudioFileClip(music_path).subclip(0, min(90, video_fragment.duration)).volumex(0.25)
    combined_audio = CompositeAudioClip([voice_clip, music_clip])
    video_fragment = video_fragment.set_audio(combined_audio)

    # Añadir subtítulos al fragmento de video
    if subtitles:
        video_fragment = video_fragment.fl(lambda gf, t: add_subtitles(gf, t, subtitles))

    # Combinar el video "hook" con el fragmento del reel
    final_clip = concatenate_videoclips([hook_clip, video_fragment])

    fragment_filename = f"reel_{fragment_index}_{video_filename}"
    fragment_path = os.path.join(LOCAL_FOLDER, fragment_filename)
    final_clip.write_videofile(fragment_path, codec='libx264', audio_codec='aac')

    # Subir el fragmento a S3
    s3_key = f"{OUTPUT_FOLDER}/{fragment_filename}"
    upload_to_s3(fragment_path, s3_key)
    os.remove(fragment_path)  # Limpiar archivos locales
    os.remove(local_hook_path)  # Limpiar el archivo hook descargado

    return fragment_filename, s3_key
