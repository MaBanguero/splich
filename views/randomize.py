from flask import render_template, request, redirect
import os
from modules.video_processing import cortar_y_mezclar_video
from config import Config  # Asegúrate de que config.py esté correctamente configurado
from . import video_bp

@video_bp.route('/randomize', methods=['GET', 'POST'])
def randomize():
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

        # Cortar y mezclar el video, luego subirlo a S3
        mixed_video_filename = cortar_y_mezclar_video(filepath, duration)
        
        return render_template('randomize.html', video=mixed_video_filename)

    return render_template('randomize.html', video=None)
