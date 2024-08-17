from flask import render_template, request, redirect
import os
from modules.video_processing import cortar_video
from config import Config  # Asegúrate de que config.py esté correctamente configurado
from . import video_bp

@video_bp.route('/segment', methods=['GET', 'POST'])
def segment():
    if request.method == 'POST':
        if 'video' not in request.files or 'duration' not in request.form:
            return redirect(request.url)

        file = request.files['video']
        duration = int(request.form['duration'])

        if file.filename == '' or duration <= 0:
            return redirect(request.url)

        # Guardar temporalmente el archivo subido
        filepath = os.path.join('/tmp', file.filename)
        file.save(filepath)

        # Cortar el video y subir los segmentos a S3
        segments = cortar_video(filepath, duration)
        
        return render_template('segment.html', segments=segments)

    return render_template('segment.html', segments=None)
