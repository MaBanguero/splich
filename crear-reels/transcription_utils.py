import boto3
import time
import json
import datetime
import uuid

def get_bucket_region(bucket_name):
    s3 = boto3.client('s3')
    response = s3.get_bucket_location(Bucket=bucket_name)
    region = response.get('LocationConstraint', 'us-east-1')  # Usar 'us-east-1' si la región no está disponible
    return region

def generate_unique_job_name(base_name):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:8]  # Genera un UUID corto
    return f"{base_name}_{timestamp}_{unique_id}"

def start_transcription_job(bucket_name, media_file_uri, output_bucket_name):
    region = get_bucket_region(bucket_name)
    transcribe = boto3.client('transcribe', region_name=region)

    transcription_job_name = generate_unique_job_name("transcription")
    transcribe.start_transcription_job(
        TranscriptionJobName=transcription_job_name,
        Media={'MediaFileUri': media_file_uri},
        MediaFormat='mp4',
        LanguageCode='es-US',  # Ajusta según sea necesario
        OutputBucketName=output_bucket_name
    )
    return transcription_job_name

def wait_for_job_completion(transcription_job_name, region):
    transcribe = boto3.client('transcribe', region_name=region)
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

def download_transcription(transcript_uri, output_bucket_name, transcript_file_name='transcription.json'):
    s3 = boto3.client('s3')
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
