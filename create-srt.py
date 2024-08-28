import boto3
import time
import json
import datetime

# AWS Transcribe and S3 clients
transcribe = boto3.client('transcribe')
s3 = boto3.client('s3')

# Configuration
transcription_job_name = 'YourJobName'
media_file_uri = 's3://facebook-videos-bucket/reels/fragment_46_0728.mp4'
output_bucket_name = 's3://facebook-videos-bucket/transcript/'
language_code = 'es-US'  # Modify if needed

def start_transcription_job():
    transcribe.start_transcription_job(
        TranscriptionJobName=transcription_job_name,
        Media={'MediaFileUri': media_file_uri},
        MediaFormat='mp4',  # or the correct format
        LanguageCode=language_code,
        OutputBucketName=output_bucket_name
    )

def wait_for_job_completion():
    while True:
        response = transcribe.get_transcription_job(TranscriptionJobName=transcription_job_name)
        status = response['TranscriptionJob']['TranscriptionJobStatus']
        if status in ['COMPLETED', 'FAILED']:
            print(f"Job {status}")
            if status == 'COMPLETED':
                return response['TranscriptionJob']['Transcript']['TranscriptFileUri']
            else:
                raise Exception("Transcription job failed")
        print("Waiting for job to complete...")
        time.sleep(30)

def download_transcription(transcript_uri):
    transcript_file_name = 'transcription.json'
    s3.download_file(output_bucket_name, transcript_uri.split('/')[-1], transcript_file_name)
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

def main():
    print("Starting transcription job...")
    start_transcription_job()

    print("Waiting for transcription to complete...")
    transcript_uri = wait_for_job_completion()

    print("Downloading transcription file...")
    transcript_file = download_transcription(transcript_uri)

    print("Converting JSON to SRT...")
    json_to_srt(transcript_file, 'output.srt')

    print("SRT file created successfully: output.srt")

if __name__ == "__main__":
    main()
