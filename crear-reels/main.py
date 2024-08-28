import os
import boto3
from s3_utils import download_from_s3, upload_to_s3
from transcription_utils import start_transcription_job, wait_for_job_completion, download_transcription, json_to_srt, get_bucket_region
from video_processing import process_single_reel
from pysrt import open as open_srt
from moviepy.editor import VideoFileClip

s3 = boto3.client('s3')
BUCKET_NAME = 'facebook-videos-bucket'
VIDEO_FOLDER = 'video-to-mix'
AUDIO_FOLDER = 'voices'
BACKGROUND_MUSIC_FOLDER = 'background-music'
HOOKS_FOLDER = 'hooks'
LOCAL_FOLDER = '/tmp'
OUTPUT_FOLDER = 'reels'
FRAGMENT_LOG_FILE = 'processed_fragments.log'
FRAGMENT_DURATION = 90

def load_processed_fragments():
    processed_fragments = {}
    if not os.path.exists(FRAGMENT_LOG_FILE):
        return processed_fragments
    with open(FRAGMENT_LOG_FILE, 'r') as log_file:
        for line in log_file:
            parts = line.strip().split(',')
            if len(parts) < 3:
                print(f"Malformed line in log file: {line}")
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

def main():
    s3_video_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=VIDEO_FOLDER).get('Contents', [])
    s3_audio_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=AUDIO_FOLDER).get('Contents', [])
    s3_music_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=BACKGROUND_MUSIC_FOLDER).get('Contents', [])
    s3_hooks_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=HOOKS_FOLDER).get('Contents', [])

    video_files = [obj['Key'] for obj in s3_video_objects if obj['Key'].endswith('.mp4')]
    audio_files = [obj['Key'] for obj in s3_audio_objects if obj['Key'].endswith('.mp3') or obj['Key'].endswith('.wav')]
    music_files = [obj['Key'] for obj in s3_music_objects if obj['Key'].endswith('.mp3') or obj['Key'].endswith('.wav')]
    hooks_files = [obj['Key'] for obj in s3_hooks_objects if obj['Key'].endswith('.mp4')]

    if not video_files or not audio_files or not music_files or not hooks_files:
        print("Missing video, audio, music, or hook files.")
        return

    processed_fragments = load_processed_fragments()

    for video_s3_key in video_files:
        video_filename = os.path.basename(video_s3_key)
        local_video_path = os.path.join(LOCAL_FOLDER, video_filename)

        if video_filename in processed_fragments and processed_fragments[video_filename]['complete']:
            print(f"Video {video_filename} already fully processed. Skipping...")
            continue

        if not os.path.exists(local_video_path):
            download_from_s3(video_s3_key, local_video_path)

        # Descargar el primer archivo de audio y música
        audio_s3_key = audio_files[0]
        music_s3_key = music_files[0]

        local_audio_path = os.path.join(LOCAL_FOLDER, os.path.basename(audio_s3_key))
        local_music_path = os.path.join(LOCAL_FOLDER, os.path.basename(music_s3_key))

        if not os.path.exists(local_audio_path):
            download_from_s3(audio_s3_key, local_audio_path)

        if not os.path.exists(local_music_path):
            download_from_s3(music_s3_key, local_music_path)

        # Obtener la región del bucket
        region = get_bucket_region(BUCKET_NAME)

        start_time = processed_fragments.get(video_filename, {}).get('last_fragment', 0) * FRAGMENT_DURATION
        fragment_index = processed_fragments.get(video_filename, {}).get('last_fragment', 0) + 1

        while start_time < VideoFileClip(local_video_path).duration:
            # Procesar un solo reel (fragmento de 90 segundos)
            fragment_filename, fragment_s3_key = process_single_reel(local_video_path, video_filename, start_time, fragment_index, local_audio_path, local_music_path, None, hooks_files)

            # Iniciar trabajo de transcripción para el fragmento
            fragment_uri = f"s3://{BUCKET_NAME}/{fragment_s3_key}"
            transcription_job_name = start_transcription_job(BUCKET_NAME, fragment_uri, BUCKET_NAME)
            transcript_uri = wait_for_job_completion(transcription_job_name, region)
            transcript_file = download_transcription(transcript_uri, BUCKET_NAME)
            srt_file = f"{os.path.splitext(fragment_filename)[0]}.srt"
            json_to_srt(transcript_file, srt_file)

            # Cargar los subtítulos
            subtitles = open_srt(srt_file)

            # Reprocesar el video con los subtítulos añadidos
            fragment_filename, fragment_s3_key = process_single_reel(local_video_path, video_filename, start_time, fragment_index, local_audio_path, local_music_path, subtitles, hooks_files)

            # Guardar el progreso del fragmento procesado
            save_processed_fragment(video_filename, fragment_index)

            start_time += FRAGMENT_DURATION
            fragment_index += 1

        save_processed_fragment(video_filename, fragment_index - 1, complete=True)
        os.remove(local_video_path)
        os.remove(local_audio_path)
        os.remove(local_music_path)

if __name__ == "__main__":
    main()
