from flask import render_template, request, redirect
import os
from modules.video_processing import agregar_inicio_final
from . import video_bp

@video_bp.route('/process_multiple', methods=['GET', 'POST'])
def process_multiple():
    if request.method == 'POST':
        video_files = request.files.getlist('videos')
        inicio_file = request.files.get('inicio')
        final_file = request.files.get('final')

        if not video_files:
            return redirect(request.url)

        input_video_paths = []
        for video_file in video_files:
            filepath = os.path.join('static/uploads/processed', video_file.filename)
            video_file.save(filepath)
            input_video_paths.append(filepath)

        inicio_path = None
        final_path = None

        if inicio_file and inicio_file.filename != '':
            inicio_path = os.path.join('static/uploads/processed', inicio_file.filename)
            inicio_file.save(inicio_path)

        if final_file and final_file.filename != '':
            final_path = os.path.join('static/uploads/processed', final_file.filename)
            final_file.save(final_path)

        videos_procesados = agregar_inicio_final(input_video_paths, inicio_path, final_path)
        return render_template('process_multiple.html', videos=videos_procesados)

    return render_template('process_multiple.html', videos=None)
