import os
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
from pysrt import SubRipFile
from s3_utils import upload_to_s3
from subtitle_utils import add_subtitles

LOCAL_FOLDER = '/tmp'
OUTPUT_FOLDER = 'reels'
FRAGMENT_DURATION = 90  # Duración de cada fragmento en segundos

def process_single_reel(video_path, video_filename, start_time, fragment_index, audio_path, music_path, subtitles):
    video_clip = VideoFileClip(video_path)
    end_time = min(start_time + FRAGMENT_DURATION, video_clip.duration)
    video_fragment = video_clip.subclip(start_time, end_time)

    # Cargar los clips de audio y música
    voice_clip = AudioFileClip(audio_path).subclip(start_time, end_time)
    music_clip = AudioFileClip(music_path).subclip(0, min(90, video_fragment.duration)).volumex(0.25)

    # Combinar la voz y la música de fondo
    combined_audio = CompositeAudioClip([voice_clip, music_clip])

    # Añadir el audio combinado al fragmento de video
    video_fragment = video_fragment.set_audio(combined_audio)

    # Añadir subtítulos al fragmento de video
    if subtitles:
        video_fragment = add_subtitles(video_fragment, subtitles)

    fragment_filename = f"reel_{fragment_index}_{video_filename}"
    fragment_path = os.path.join(LOCAL_FOLDER, fragment_filename)
    video_fragment.write_videofile(fragment_path, codec='libx264', audio_codec='aac')

    # Subir el fragmento a S3
    s3_key = f"{OUTPUT_FOLDER}/{fragment_filename}"
    upload_to_s3(fragment_path, s3_key)
    os.remove(fragment_path)  # Limpiar archivos locales

    return fragment_filename, s3_key
