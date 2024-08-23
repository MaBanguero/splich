import os
import boto3

s3 = boto3.client('s3')
BUCKET_NAME = 'facebook-videos-bucket'
REEL_FOLDER = 'reels'
FRAGMENT_LOG_FILE = 'processed_fragments.log'

def initialize_log_from_reels():
    # Obtener todos los archivos en la carpeta 'reels'
    s3_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=REEL_FOLDER).get('Contents', [])
    processed_fragments = {}

    for obj in s3_objects:
        # Extraer el nombre del video y el fragmento del archivo
        fragment_filename = os.path.basename(obj['Key'])
        if fragment_filename.startswith('fragment_'):
            parts = fragment_filename.split('_')
            fragment_index = int(parts[1])
            video_filename = '_'.join(parts[2:])

            # Actualizar el fragmento máximo procesado por video
            if video_filename in processed_fragments:
                processed_fragments[video_filename] = max(processed_fragments[video_filename], fragment_index)
            else:
                processed_fragments[video_filename] = fragment_index

    # Escribir el log de fragmentos procesados
    with open(FRAGMENT_LOG_FILE, 'w') as log_file:
        for video_filename, last_fragment in processed_fragments.items():
            log_file.write(f"{video_filename},{last_fragment}\n")
    
    print(f"Log inicializado con {len(processed_fragments)} videos.")

if __name__ == "__main__":
    initialize_log_from_reels()
