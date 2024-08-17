import os

class Config:
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 60 * 1024 * 1024 * 1024  # 500 MB max file size
    LOG_FOLDER = 'logs'
    SUBFOLDERS = ['segments', 'randomized', 'processed', 'duplicate_voice', 'tts']
    GCS_CREDENTIALS_FILE = '/home/marvin/modern-heading-280420-358a869141f1.json'
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'facebook-videos-bucket')