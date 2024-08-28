import os
import boto3
from s3_utils import download_from_s3, upload_to_s3
from transcription_utils import start_transcription_job, wait_for_job_completion, download_transcription, json_to_srt, get_bucket_region
from video_processing import process_video_fragment
from pysrt import open as open_srt
from moviepy.editor import VideoFileClip, AudioFileClip

s3 = boto3.client('s3')

BUCKET_NAME = 'facebook-videos-bucket'
VIDEO_FOLDER = 'video-to-mix'
AUDIO_FOLDER = 'voices'
BACKGROUND_MUSIC_FOLDER = 'background-music'
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
    # Obtener la lista de videos, audios y música de fondo desde S3
    s3_video_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=VIDEO_FOLDER).get('Contents', [])
    s3_audio_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=AUDIO_FOLDER).get('Contents', [])
    s3_music_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=BACKGROUND_MUSIC_FOLDER).get('Contents', [])

    video_files = [obj['Key'] for obj in s3_video_objects if obj['Key'].endswith('.mp4')]
    audio_files = [obj['Key'] for obj in s3_audio_objects if obj['Key'].endswith('.mp3') or obj['Key'].endswith('.wav')]
    music_files = [obj['Key'] for obj in s3_music_objects if obj['Key'].endswith('.mp3') or obj['Key'].endswith('.wav')]

    if not video_files or not audio_files or not music_files:
        print("No video, audio, or background music files found.")
        return

    # Cargar los fragmentos procesados anteriormente
    processed_fragments = load_processed_fragments()

    for video_s3_key in video_files:
        video_filename = os.path.basename(video_s3_key)
        audio_s3_key = audio_files[0]
        music_s3_key = music_files[0]

        local_video_path = os.path.join(LOCAL_FOLDER, video_filename)
        local_audio_path = os.path.join(LOCAL_FOLDER, os.path.basename(audio_s3_key))
        local_music_path = os.path.join(LOCAL_FOLDER, os.path.basename(music_s3_key))

        if video_filename in processed_fragments and processed_fragments[video_filename]['complete']:
            print(f"Video {video_filename} already fully processed. Skipping...")
            continue

        if not os.path.exists(local_video_path):
            download_from_s3(video_s3_key, local_video_path)

        if not os.path.exists(local_audio_path):
            download_from_s3(audio_s3_key, local_audio_path)

        if not os.path.exists(local_music_path):
            download_from_s3(music_s3_key, local_music_path)

        # Obtener la región del bucket
        region = get_bucket_region(BUCKET_NAME)

        # Generar un nombre único y empezar el trabajo de transcripción
        media_file_uri = f"s3://{BUCKET_NAME}/{video_s3_key}"
        output_bucket_name = f"s3://{BUCKET_NAME}/transcript/"

        transcription_job_name = start_transcription_job(BUCKET_NAME, media_file_uri, output_bucket_name)
        transcript_uri = wait_for_job_completion(transcription_job_name, region)
        transcript_file = download_transcription(transcript_uri, output_bucket_name)
        srt_file = f"{os.path.splitext(video_filename)[0]}.srt"
        json_to_srt(transcript_file, srt_file)

        # Cargar los subtítulos y preparar el video y el audio
        subtitles = open_srt(srt_file)
        video_clip = VideoFileClip(local_video_path)
        audio_clip = AudioFileClip(local_audio_path)
        music_clip = AudioFileClip(local_music_path).volumex(0.25)

        start_time = processed_fragments.get(video_filename, {}).get('last_fragment', 0) * FRAGMENT_DURATION
        fragment_index = processed_fragments.get(video_filename, {}).get('last_fragment', 0) + 1

        while start_time < video_clip.duration:
            fragment_path = process_video_fragment(
                video_clip, audio_clip, music_clip, start_time, fragment_index, video_filename, subtitles
            )

            upload_to_s3(fragment_path, f"{OUTPUT_FOLDER}/{os.path.basename(fragment_path)}")
            os.remove(fragment_path)

            save_processed_fragment(video_filename, fragment_index)

            start_time += FRAGMENT_DURATION
            fragment_index += 1

        save_processed_fragment(video_filename, fragment_index - 1, complete=True)
        os.remove(local_video_path)
        os.remove(local_audio_path)
        os.remove(local_music_path)

if __name__ == "__main__":
    main()
