import os
import logging
import zipfile
from flask import Flask, request, render_template, redirect, url_for, send_file, abort
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip, ImageClip
from moviepy.audio.fx.all import audio_loop
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import random
import pyttsx3
from pydub import AudioSegment
from pydub.playback import play
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import storage
import io, sys
from google.oauth2 import service_account
import gc

credentials = service_account.Credentials.from_service_account_file(
    '/home/marvin/modern-heading-280420-358a869141f1.json'
)

storage_client = storage.Client(credentials=credentials)

app = Flask(__name__)
base_upload_folder = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = base_upload_folder
app.config['MAX_CONTENT_LENGTH'] = 60 * 1024 * 1024 * 1024   # 500 MB max file size

# Crear subdirectorios para cada funcionalidad si no existen
subfolders = ['segments', 'randomized', 'processed', 'duplicate_voice', 'tts']
for folder in subfolders:
    path = os.path.join(base_upload_folder, folder)
    if not os.path.exists(path):
        os.makedirs(path)

if not os.path.exists('logs'):
    os.makedirs('logs')

file_handler = logging.FileHandler('logs/flask.log')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
file_handler.setFormatter(formatter)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)

app.logger.info('Flask application starting up')

duplicated_voice_path = None

def cortar_video(input_video_path, duracion_segmento, inicio_path=None, final_path=None):
    video = VideoFileClip(input_video_path)
    duracion_total = int(video.duration)
    segments = []

    inicio_clip = VideoFileClip(inicio_path) if inicio_path else None
    final_clip = VideoFileClip(final_path) if final_path else None

    for start_time in range(0, duracion_total, duracion_segmento):
        end_time = min(start_time + duracion_segmento, duracion_total)
        clip = video.subclip(start_time, end_time)
        clips = [clip]
        if inicio_clip:
            clips.insert(0, inicio_clip)
        if final_clip:
            clips.append(final_clip)
        combined_clip = concatenate_videoclips(clips)

        output_filename = f"segmento_{start_time}_{end_time}.mp4"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'segments', output_filename)
        combined_clip.write_videofile(output_path, codec='libx264', audio_codec='aac')
        segments.append(output_filename)

    return segments

def cortar_y_mezclar_video(input_video_path, duracion_segmento):
    video = VideoFileClip(input_video_path)
    duracion_total = int(video.duration)
    clips = []

    for start_time in range(0, duracion_total, duracion_segmento):
        end_time = min(start_time + duracion_segmento, duracion_total)
        clip = video.subclip(start_time, end_time)
        clips.append(clip)

    random.shuffle(clips)
    video_final = concatenate_videoclips(clips)
    output_filename = "video_mezclado.mp4"
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'randomized', output_filename)
    video_final.write_videofile(output_path, codec='libx264', audio_codec='aac')

    return output_filename

def agregar_inicio_final(input_video_paths, inicio_path=None, final_path=None):
    videos_procesados = []

    inicio_clip = VideoFileClip(inicio_path) if inicio_path else None
    final_clip = VideoFileClip(final_path) if final_path else None

    for input_video_path in input_video_paths:
        video = VideoFileClip(input_video_path)
        clips = [video]
        if inicio_clip:
            clips.insert(0, inicio_clip)
        if final_clip:
            clips.append(final_clip)
        combined_clip = concatenate_videoclips(clips)

        output_filename = f"procesado_{os.path.basename(input_video_path)}"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'processed', output_filename)
        combined_clip.write_videofile(output_path, codec='libx264', audio_codec='aac')
        videos_procesados.append(output_filename)

    return videos_procesados

def create_subtitle_image(text, font_path='Poppins-Regular.ttf', font_size=40, text_color="white", bg_color="black", width=620):
    font = ImageFont.truetype(font_path, font_size)
    image = Image.new("RGB", (width, font_size * 2), color=bg_color)
    draw = ImageDraw.Draw(image)
    w, h = draw.textsize(text, font=font)
    draw.text(((width - w) / 2, (font_size - h) / 2), text, font=font, fill=text_color, align='center', xy=[])
    return image

def add_subtitles_to_video(video_path, subtitles, audio_path, output_path):
    video = VideoFileClip(video_path).without_audio()
    new_audio = AudioFileClip(audio_path)

    subtitle_clips = []
    for start, end, text in subtitles:
        subtitle_image = create_subtitle_image(text)
        subtitle_clip = (ImageClip(np.array(subtitle_image))
                         .set_start(start)
                         .set_end(end)
                         .set_position(("center", "bottom"))
                         .set_duration(end - start)
                         .set_opacity(0.8))  # Adjust opacity as needed
        subtitle_clips.append(subtitle_clip)

    final_video = CompositeVideoClip([video, *subtitle_clips]).set_audio(new_audio)
    final_video.write_videofile(output_path, codec="libx264", fps=24)

def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    """Sube un archivo al bucket de GCS."""
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    
    if blob.exists(storage_client):
        print(f"El archivo {destination_blob_name} ya existe en el bucket {bucket_name}.")
        return f'gs://{bucket_name}/{destination_blob_name}'
    
    blob.upload_from_filename(source_file_name)
    return f'gs://{bucket_name}/{destination_blob_name}'
    
def transcribe_audio(audio_path, bucket_name):
    client = speech.SpeechClient(credentials=credentials)

    # Dividir el archivo de audio en segmentos más pequeños
    audio = AudioSegment.from_file(audio_path)
    sample_rate = audio.frame_rate
    print(sample_rate)
    segment_length_ms = 60 * 1000  # 1 minuto en milisegundos
    segments = [audio[i:i + segment_length_ms] for i in range(0, len(audio), segment_length_ms)]
    
    subtitles = []
    start_time_offset = 0  # Para ajustar el tiempo de inicio de cada segmento
    for i, segment in enumerate(segments):
        segment_filename = f'segment_{i}.wav'
        segment_path = os.path.join(app.config['UPLOAD_FOLDER'], 'subtitles', segment_filename)
        segment.export(segment_path, format="wav")
        
        gcs_uri = upload_to_gcs(bucket_name, segment_path, segment_filename)
        
        audio = speech.RecognitionAudio(uri=gcs_uri)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            language_code="es-US",
        )
        
        operation = client.long_running_recognize(config=config, audio=audio)
        response = operation.result(timeout=600)
        
        for result in response.results:
            alternative = result.alternatives[0]
            start_time = start_time_offset + result.result_end_time.total_seconds() - len(alternative.transcript.split()) * 0.5
            end_time = start_time_offset + result.result_end_time.total_seconds()
            subtitles.append((start_time, end_time, alternative.transcript))
        
        start_time_offset += segment_length_ms / 1000  # Ajustar el tiempo de inicio para el siguiente segmento
    
    return subtitles

def add_logo_and_background_audio(video_path, logo_path, audio_path, output_path, logo_position=("center", "top")):
    # Cargar el video
    video = VideoFileClip(video_path)
    
    # Cargar el logo
    logo = (ImageClip(logo_path)
            .set_duration(video.duration)
            .resize(height=50)  # Cambiar el tamaño del logo
            .set_position(logo_position)  # Posición del logo
            .set_opacity(0.5))  # Opacidad del logo

    # Cargar el audio de fondo
    background_audio = AudioFileClip(audio_path)
    
    # Repetir el audio para que coincida con la duración del video
    if background_audio.duration < video.duration:
        background_audio = audio_loop(background_audio, duration=video.duration)

    # Crear el video con el logo superpuesto
    final_video = CompositeVideoClip([video, logo])
    
    # Agregar el audio de fondo
    final_video = final_video.set_audio(background_audio)

    # Exportar el video final
    final_video.write_videofile(output_path, codec='libx264', audio_codec='aac')

@app.route('/')
def home():
    app.logger.info('Home page accessed')
    return render_template('home.html')

@app.route('/segment', methods=['GET', 'POST'])
def segment():
    if request.method == 'POST':
        if 'video' not in request.files or 'duration' not in request.form:
            return redirect(request.url)

        file = request.files['video']
        inicio_file = request.files.get('inicio')
        final_file = request.files.get('final')
        duration = int(request.form['duration'])

        if file.filename == '' or duration <= 0:
            return redirect(request.url)

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'segments', file.filename)
        file.save(filepath)

        inicio_path = None
        final_path = None

        if inicio_file and inicio_file.filename != '':
            inicio_path = os.path.join(app.config['UPLOAD_FOLDER'], 'segments', inicio_file.filename)
            inicio_file.save(inicio_path)

        if final_file and final_file.filename != '':
            final_path = os.path.join(app.config['UPLOAD_FOLDER'], 'segments', final_file.filename)
            final_file.save(final_path)

        segments = cortar_video(filepath, duration, inicio_path, final_path)
        return render_template('segment.html', segments=segments)

    return render_template('segment.html', segments=None)

@app.route('/randomize', methods=['GET', 'POST'])
def randomize():
    if request.method == 'POST':
        if 'video' not in request.files or 'duration' not in request.form:
            return redirect(request.url)

        file = request.files['video']
        duration = int(request.form['duration'])

        if file.filename == '' or duration <= 0:
            return redirect(request.url)

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'randomized', file.filename)
        file.save(filepath)

        mixed_video_filename = cortar_y_mezclar_video(filepath, duration)
        return render_template('randomize.html', video=mixed_video_filename)

    return render_template('randomize.html', video=None)

@app.route('/process_multiple', methods=['GET', 'POST'])
def process_multiple():
    if request.method == 'POST':
        video_files = request.files.getlist('videos')
        inicio_file = request.files.get('inicio')
        final_file = request.files.get('final')

        if not video_files:
            return redirect(request.url)

        input_video_paths = []
        for video_file in video_files:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'processed', video_file.filename)
            video_file.save(filepath)
            input_video_paths.append(filepath)

        inicio_path = None
        final_path = None

        if inicio_file and inicio_file.filename != '':
            inicio_path = os.path.join(app.config['UPLOAD_FOLDER'], 'processed', inicio_file.filename)
            inicio_file.save(inicio_path)

        if final_file and final_file.filename != '':
            final_path = os.path.join(app.config['UPLOAD_FOLDER'], 'processed', final_file.filename)
            final_file.save(final_path)

        videos_procesados = agregar_inicio_final(input_video_paths, inicio_path, final_path)
        return render_template('process_multiple.html', videos=videos_procesados)

    return render_template('process_multiple.html', videos=None)

@app.route('/download/<folder>/<filename>')
def download(folder, filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], folder, filename)
    if os.path.exists(file_path):
        app.logger.info(f'Download requested for {filename}')
        return send_file(file_path, as_attachment=True, download_name=filename)
    else:
        app.logger.warning(f'File {filename} not found for download')
        abort(404)

@app.route('/download_all')
def download_all():
    zip_filename = "all_files.zip"
    zip_filepath = os.path.join(app.config['UPLOAD_FOLDER'], zip_filename)

    with zipfile.ZipFile(zip_filepath, 'w') as zipf:
        for folder in subfolders:
            folder_path = os.path.join(app.config['UPLOAD_FOLDER'], folder)
            for root, _, files in os.walk(folder_path):
                for file in files:
                    zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), app.config['UPLOAD_FOLDER']))

    return send_file(zip_filepath, as_attachment=True, download_name=zip_filename)

# Nueva funcionalidad para duplicar voz y generar TTS
@app.route('/duplicate_voice', methods=['GET', 'POST'])
def duplicate_voice():
    global duplicated_voice_path

    if request.method == 'POST':
        if 'audio' not in request.files:
            return redirect(request.url)

        file = request.files['audio']

        if file.filename == '':
            return redirect(request.url)

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'duplicate_voice', file.filename)
        file.save(filepath)

        # Duplicar el archivo de audio
        audio = AudioSegment.from_file(filepath)
        duplicated_audio = audio + audio  # Duplica el audio concatenándolo consigo mismo
        duplicated_voice_path = os.path.join(app.config['UPLOAD_FOLDER'], 'duplicate_voice', 'duplicated_' + file.filename)
        duplicated_audio.export(duplicated_voice_path, format="wav")

        return send_file(duplicated_voice_path, as_attachment=True, download_name='duplicated_' + file.filename)

    return render_template('duplicate_voice.html')

@app.route('/text_to_speech', methods=['GET', 'POST'])
def text_to_speech():
    global duplicated_voice_path

    if request.method == 'POST':
        text = request.form.get('text')
        if not text:
            return redirect(request.url)

        tts_output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'tts', 'tts_output.wav')

        if duplicated_voice_path:
            # Usa la voz duplicada para el TTS
            engine = pyttsx3.init()
            engine.save_to_file(text, tts_output_path)
            engine.runAndWait()

            # Combina la voz duplicada con el TTS
            duplicated_audio = AudioSegment.from_file(duplicated_voice_path)
            tts_audio = AudioSegment.from_file(tts_output_path)
            combined_audio = duplicated_audio.overlay(tts_audio)
            combined_audio.export(tts_output_path, format="wav")
        else:
            # Si no hay voz duplicada, solo usa TTS
            engine = pyttsx3.init()
            engine.save_to_file(text, tts_output_path)
            engine.runAndWait()

        return send_file(tts_output_path, as_attachment=True, download_name='tts_output.wav')

    return render_template('text_to_speech.html')

@app.route('/add_subtitles', methods=['GET', 'POST'])
def add_subtitles():
    if request.method == 'POST':
        if 'video' not in request.files or 'audio' not in request.files:
            return redirect(request.url)

        video_file = request.files['video']
        audio_file = request.files['audio']

        if video_file.filename == '' or audio_file.filename == '':
            return redirect(request.url)

        video_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'subtitles', video_file.filename)
        audio_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'subtitles', audio_file.filename)

        video_file.save(video_filepath)
        audio_file.save(audio_filepath)

        # Transcribir el audio para generar subtítulos automáticamente
        subtitles = transcribe_audio(audio_filepath, 'contenido-bucket')

        output_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'subtitles', 'output_' + video_file.filename)
        add_subtitles_to_video(video_filepath, subtitles, audio_filepath, output_filepath)

        return send_file(output_filepath, as_attachment=True, download_name='output_' + video_file.filename)

    return render_template('add_subtitles.html')

@app.route('/add_logo_audio', methods=['GET', 'POST'])
def add_logo_audio():
    if request.method == 'POST':
        if 'video' not in request.files or 'logo' not in request.files or 'audio' not in request.files:
            return redirect(request.url)

        video_file = request.files['video']
        logo_file = request.files['logo']
        audio_file = request.files['audio']

        if video_file.filename == '' or logo_file.filename == '' or audio_file.filename == '':
            return redirect(request.url)

        video_path = os.path.join(app.config['UPLOAD_FOLDER'], 'logo_audio', video_file.filename)
        logo_path = os.path.join(app.config['UPLOAD_FOLDER'], 'logo_audio', logo_file.filename)
        audio_path = os.path.join(app.config['UPLOAD_FOLDER'], 'logo_audio', audio_file.filename)

        video_file.save(video_path)
        logo_file.save(logo_path)
        audio_file.save(audio_path)

        output_filename = f"logo_audio_{video_file.filename}"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'logo_audio', output_filename)

        add_logo_and_background_audio(video_path, logo_path, audio_path, output_path)

        return render_template('add_logo_audio.html', video=output_filename)

    return render_template('add_logo_audio.html', video=None)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
