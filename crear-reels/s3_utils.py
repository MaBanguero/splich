import boto3

s3 = boto3.client('s3')
BUCKET_NAME = 'facebook-videos-bucket'

def download_from_s3(s3_key, local_path):
    s3.download_file(BUCKET_NAME, s3_key, local_path)
    print(f"Downloaded {s3_key} to {local_path}")

def upload_to_s3(local_path, s3_key):
    s3.upload_file(local_path, BUCKET_NAME, s3_key)
    print(f"Uploaded {local_path} to {s3_key}")
