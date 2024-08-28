import os
import time
import json
import datetime
import boto3
import cv2
import uuid
import moviepy.editor as mp
from moviepy.video.io.VideoFileClip import VideoFileClip
from pysrt import open as open_srt

# AWS clients
transcribe = boto3.client('transcribe', region_name='us-east-2')
s3 = boto3.client('s3')

# Configuration
BUCKET_NAME = 'facebook-videos-bucket'
VIDEO_FOLDER = 'video-to-mix'
AUDIO_FOLDER = 'voices'
BACKGROUND_MUSIC_FOLDER = 'background-music'
LOCAL_FOLDER = '/tmp'
OUTPUT_FOLDER = 'reels'
FRAGMENT_DURATION = 90  # Duration in seconds for each fragment
FRAGMENT_LOG_FILE = 'processed_fragments.log'  # Log file to track processed fragments
transcription_job_name = 'YourJobName'
language_code = 'es-US'  # Modify if needed

def download_from_s3(s3_key, local_path):
    # Check if the file already exists
    if os.path.exists(local_path):
        print(f"File {local_path} already exists. Skipping download.")
        return

    # Ensure the directory exists
    local_dir = os.path.dirname(local_path)
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)

    # Download the file from S3
    s3.download_file(BUCKET_NAME, s3_key, local_path)
    print(f"Downloaded {s3_key} to {local_path}")



def start_transcription_job(media_file_uri):
    unique_job_name = f"{transcription_job_name}_{uuid.uuid4()}"
    try:
        response = transcribe.start_transcription_job(
            TranscriptionJobName=unique_job_name,
            Media={'MediaFileUri': media_file_uri},
            MediaFormat='mp4',
            LanguageCode=language_code,
            OutputBucketName=BUCKET_NAME
        )
        print(f"Started transcription job: {unique_job_name}")
        return response
    except Exception as e:
        print(f"Error starting transcription job: {str(e)}")
        raise

def wait_for_job_completion():
    while True:
        response = transcribe.get_transcription_job(TranscriptionJobName=transcription_job_name)
        status = response['TranscriptionJob']['TranscriptionJobStatus']
        if status in ['COMPLETED', 'FAILED']:
            if status == 'COMPLETED':
                return response['TranscriptionJob']['Transcript']['TranscriptFileUri']
            else:
                raise Exception("Transcription job failed")
        time.sleep(30)

def download_transcription(transcript_uri):
    transcript_file_name = os.path.join(LOCAL_FOLDER, 'transcription.json')
    s3.download_file(BUCKET_NAME, transcript_uri.split('/')[-1], transcript_file_name)
    return transcript_file_name

def json_to_srt(json_file, srt_file):
    with open(json_file, 'r') as f:
        data = json.load(f)

    with open(srt_file, 'w') as f:
        index = 1
        for item in data['results']['items']:
            if 'start_time' in item:
                start_time = float(item['start_time'])
                end_time = float(item['end_time'])
                f.write(f"{index}\n")
                f.write(f"{format_timestamp(start_time)} --> {format_timestamp(end_time)}\n")
                f.write(f"{item['alternatives'][0]['content']}\n\n")
                index += 1

def format_timestamp(seconds):
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = int((td.total_seconds() - total_seconds) * 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

def get_text_size(text, font, font_scale, thickness):
    size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    return size

def split_text(text, max_width, font, font_scale, thickness):
    words = text.split()
    line1 = ""
    line2 = ""
    
    for word in words:
        if get_text_size(line1 + word, font, font_scale, thickness)[0] <= max_width:
            line1 += word + " "
        else:
            if get_text_size(line2 + word, font, font_scale, thickness)[0] <= max_width:
                line2 += word + " "
    
    return line1.strip(), line2.strip()

def draw_background(frame, line1, line2, font, font_scale, thickness, elapsed_ratio, text_positions):
    words_line1 = line1.split()
    words_line2 = line2.split()

    total_words = len(words_line1) + len(words_line2)
    word_index = int(elapsed_ratio * total_words)

    if word_index < len(words_line1):
        word = words_line1[word_index]
        x, y = text_positions[0]
        for i, w in enumerate(words_line1[:word_index]):
            x += get_text_size(w, font, font_scale, thickness)[0] + 20
    else:
        word = words_line2[word_index - len(words_line1)]
        x, y = text_positions[1]
        for i, w in enumerate(words_line2[:word_index - len(words_line1)]):
            x += get_text_size(w, font, font_scale, thickness)[0] + 20

    word_size = get_text_size(word, font, font_scale, thickness)
    end_x = x + word_size[0]
    cv2.rectangle(frame, (x - 5, y - word_size[1] - 10), (end_x + 5, y + 10), (128, 0, 128), -1)
    
    cv2.putText(frame, word, (x, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)

def add_subtitles(get_frame, t, subtitles):
    frame = get_frame(t)
    frame_cv2 = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    
    frame_height, frame_width, _ = frame_cv2.shape
    margin = int(frame_width * 0.1)
    safe_width = frame_width - 2 * margin
    elapsed_ratio = (t % 2) / 2

    for subtitle in subtitles:
        if subtitle.start.ordinal <= t*1000 < subtitle.end.ordinal:
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.6
            thickness = 3

            line1, line2 = split_text(subtitle.text, safe_width, font, font_scale, thickness)

            text_size_line1 = get_text_size(line1, font, font_scale, thickness)
            text_size_line2 = get_text_size(line2, font, font_scale, thickness)
            text_x_line1 = (frame_width - text_size_line1[0]) // 2
            text_x_line2 = (frame_width - text_size_line2[0]) // 2
            text_y_line1 = (frame_height + text_size_line1[1]) // 2 - 30
            text_y_line2 = (frame_height + text_size_line1[1]) // 2 + 20

            text_positions = [(text_x_line1, text_y_line1), (text_x_line2, text_y_line2)]
            draw_background(frame_cv2, line1, line2, font, font_scale, thickness, elapsed_ratio, text_positions)
            
            x = text_x_line1
            for word in line1.split():
                cv2.putText(frame_cv2, word, (x, text_y_line1), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
                x += get_text_size(word, font, font_scale, thickness)[0] + 20

            x = text_x_line2
            for word in line2.split():
                cv2.putText(frame_cv2, word, (x, text_y_line2), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
                x += get_text_size(word, font, font_scale, thickness)[0] + 20
            
            break

    return cv2.cvtColor(frame_cv2, cv2.COLOR_BGR2RGB)

def process_video(video_filename, audio_filename, music_filename, srt_filename):
    local_video_path = os.path.join(LOCAL_FOLDER, video_filename)
    local_audio_path = os.path.join(LOCAL_FOLDER, audio_filename)
    local_music_path = os.path.join(LOCAL_FOLDER, music_filename)

    # Process video in fragments
    video_clip = VideoFileClip(local_video_path)
    audio_clip = mp.AudioFileClip(local_audio_path)
    music_clip = mp.AudioFileClip(local_music_path).volumex(0.25)  # Reduce music volume to 25%

    subtitles = open_srt(srt_filename)

    for i in range(0, int(video_clip.duration), FRAGMENT_DURATION):
        start_time = i
        end_time = min(i + FRAGMENT_DURATION, video_clip.duration)
        video_fragment = video_clip.subclip(start_time, end_time)
        voice_fragment = audio_clip.subclip(start_time, end_time)
        music_fragment = music_clip.subclip(0, min(90, video_fragment.duration))

        combined_audio = mp.CompositeAudioClip([voice_fragment, music_fragment])
        final_video_fragment = video_fragment.set_audio(combined_audio)
        video_with_subtitles = final_video_fragment.fl(lambda gf, t: add_subtitles(gf, t, subtitles))

        fragment_filename = f"fragment_{i // FRAGMENT_DURATION}_{video_filename}"
        fragment_path = os.path.join(LOCAL_FOLDER, fragment_filename)
        video_with_subtitles.write_videofile(fragment_path, codec='libx264', audio_codec='aac')

        upload_to_s3(fragment_path, f"{OUTPUT_FOLDER}/{fragment_filename}")
        os.remove(fragment_path)

def upload_to_s3(local_path, s3_key):
    s3.upload_file(local_path, BUCKET_NAME, s3_key)
    print(f"Uploaded {local_path} to {s3_key}")
    
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

def main():
    s3_video_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=VIDEO_FOLDER).get('Contents', [])
    s3_audio_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=AUDIO_FOLDER).get('Contents', [])
    s3_music_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=BACKGROUND_MUSIC_FOLDER).get('Contents', [])

    video_files = [obj['Key'] for obj in s3_video_objects if obj['Key'].endswith('.mp4')]
    audio_files = [obj['Key'] for obj in s3_audio_objects if obj['Key'].endswith('.mp3') or obj['Key'].endswith('.wav')]
    music_files = [obj['Key'] for obj in s3_music_objects if obj['Key'].endswith('.mp3') or obj['Key'].endswith('.wav')]

    if not video_files or not audio_files or not music_files:
        print("No se encontraron archivos de video, audio o música de fondo.")
        return

    processed_fragments = load_processed_fragments()

    for video_s3_key in video_files:
        video_filename = os.path.basename(video_s3_key)
        audio_s3_key = audio_files[0]
        music_s3_key = music_files[0]

        audio_filename = os.path.basename(audio_s3_key)
        music_filename = os.path.basename(music_s3_key)

        if video_filename in processed_fragments and processed_fragments[video_filename]['complete']:
            print(f"El video {video_filename} ya ha sido procesado completamente. Saltando...")
            continue

        local_video_path = os.path.join(LOCAL_FOLDER, video_filename)
        local_audio_path = os.path.join(LOCAL_FOLDER, audio_filename)
        local_music_path = os.path.join(LOCAL_FOLDER, music_filename)

        download_from_s3(video_s3_key, local_video_path)
        download_from_s3(audio_s3_key, local_audio_path)
        download_from_s3(music_s3_key, local_music_path)

        video_clip = VideoFileClip(local_video_path)
        fragment_index = 1
        for start_time in range(0, int(video_clip.duration), FRAGMENT_DURATION):
            end_time = min(start_time + FRAGMENT_DURATION, video_clip.duration)
            reel_fragment = video_clip.subclip(start_time, end_time)
            
            fragment_filename = f"reel_fragment_{fragment_index}_{video_filename}"
            fragment_path = os.path.join(LOCAL_FOLDER, fragment_filename)

            reel_fragment.write_videofile(fragment_path, codec='libx264', audio_codec='aac')

            reel_s3_key = f"{OUTPUT_FOLDER}/{fragment_filename}"
            upload_to_s3(fragment_path, reel_s3_key)

            reel_media_uri = f"s3://{BUCKET_NAME}/{reel_s3_key}"
            start_transcription_job(reel_media_uri)

            transcript_uri = wait_for_job_completion()
            transcript_file = download_transcription(transcript_uri)

            srt_filename = os.path.join(LOCAL_FOLDER, f"{fragment_filename}.srt")
            json_to_srt(transcript_file, srt_filename)

            process_video(fragment_filename, audio_filename, music_filename, srt_filename)

            save_processed_fragment(video_filename, fragment_index, complete=True)

            os.remove(fragment_path)
            os.remove(transcript_file)
            os.remove(srt_filename)

            fragment_index += 1

        os.remove(local_video_path)
        os.remove(local_audio_path)
        os.remove(local_music_path)

if __name__ == "__main__":
    main()
