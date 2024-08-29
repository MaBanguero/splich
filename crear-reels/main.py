import os
import boto3
from s3_utils import download_from_s3, upload_to_s3
from video_processing import process_single_reel
from pysrt import open as open_srt
from transcription_utils import get_bucket_region
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
    s3_music_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=BACKGROUND_MUSIC_FOLDER).get('Contents', [])
    s3_hooks_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=HOOKS_FOLDER).get('Contents', [])
    s3_voices_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=AUDIO_FOLDER).get('Contents', [])

    video_files = [obj['Key'] for obj in s3_video_objects if obj['Key'].endswith('.mp4')]
    music_files = [obj['Key'] for obj in s3_music_objects if obj['Key'].endswith('.mp3') or obj['Key'].endswith('.wav')]
    hooks_files = [obj['Key'] for obj in s3_hooks_objects if obj['Key'].endswith('.mp4')]
    voices_files = [obj['Key'] for obj in s3_voices_objects if obj['Key'].endswith('.mp3') or obj['Key'].endswith('.wav')]

    if not video_files or not music_files or not hooks_files or not voices_files:
        print("Missing video, music, hook, or voice files.")
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

        # Descargar el primer archivo de música
        music_s3_key = music_files[0]
        local_music_path = os.path.join(LOCAL_FOLDER, os.path.basename(music_s3_key))

        if not os.path.exists(local_music_path):
            download_from_s3(music_s3_key, local_music_path)

        start_time = processed_fragments.get(video_filename, {}).get('last_fragment', 0) * FRAGMENT_DURATION
        fragment_index = processed_fragments.get(video_filename, {}).get('last_fragment', 0) + 1

        while start_time < VideoFileClip(local_video_path).duration:
            # Procesar un solo reel (fragmento de 90 segundos)
            fragment_filename, fragment_s3_key = process_single_reel(
                video_path=local_video_path,
                video_filename=video_filename,
                start_time=start_time,
                fragment_index=fragment_index,
                music_path=local_music_path,
                hooks=hooks_files,
                voices=voices_files,  # Se incluye el argumento 'voices'
                bucket_name=BUCKET_NAME
            )

            # Guardar el progreso del fragmento procesado
            save_processed_fragment(video_filename, fragment_index)

            start_time += FRAGMENT_DURATION
            fragment_index += 1

        save_processed_fragment(video_filename, fragment_index - 1, complete=True)
        os.remove(local_video_path)
        os.remove(local_music_path)

if __name__ == "__main__":
    main()
