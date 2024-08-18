from modules.facebook_reel_uploader import FacebookReelsUploader

# Configura tus credenciales y detalles del video
access_token = 'EAALb4JjxP1ABOzicDhk7HsA2ZAU7ZAjVIZAqDV3zZBVnh6yAuYLkSkZBJW8uY0jZBTY2qEZCd65CU5L5fYSoTlLgFQgOLYMJA3TBxbJs9L6dB5rZBvIg6mcKWyeZBHYWmku1CdNk1QCKlCkbo1Hs59X0rI3TZBnpdPsYZBFW78kSM2W4yPHZBZAfkhUKXtdGBSu9FzwCC7wRsxZCM74hahLzOkSlMI2KMZD'
page_id = '438383526014976'
video_title = '5 Cosas que no sabias'
video_description = 'Dale like y comenta'

uploader = FacebookReelsUploader(access_token, page_id)
upload_thread = uploader.start_uploading_in_background(video_title, video_description)
upload_thread.join()  # Espera a que el hilo termine antes de salir del programa

