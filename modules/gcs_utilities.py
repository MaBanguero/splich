from google.cloud import storage, speech_v1p1beta1 as speech
from google.oauth2 import service_account
import os

def get_storage_client(credentials_path):
    credentials = service_account.Credentials.from_service_account_file(credentials_path)
    return storage.Client(credentials=credentials)

def upload_to_gcs(storage_client, bucket_name, source_file_name, destination_blob_name):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    if blob.exists(storage_client):
        print(f"El archivo {destination_blob_name} ya existe en el bucket {bucket_name}.")
        return f'gs://{bucket_name}/{destination_blob_name}'

    blob.upload_from_filename(source_file_name)
    return f'gs://{bucket_name}/{destination_blob_name}'
