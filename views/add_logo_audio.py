from flask import render_template, request, redirect, send_file
import os
from modules.video_processing import add_logo_and_background_audio
from . import video_bp

@video_bp.route('/add_logo_audio', methods=['GET', 'POST'])
def add_logo_audio():
    if request.method == 'POST':
        if 'video' not in request.files or 'logo' not in request.files or 'audio' not in request.files:
            return redirect(request.url)

        video_file = request.files['video']
        logo_file = request.files['logo']
        audio_file = request.files['audio']

        if video_file.filename == '' or logo_file.filename == '' or audio_file.filename == '':
            return redirect(request.url)

        video_path = os.path.join('static/uploads/logo_audio', video_file.filename)
        logo_path = os.path.join('static/uploads/logo_audio', logo_file.filename)
        audio_path = os.path.join('static/uploads/logo_audio', audio_file.filename)

        video_file.save(video_path)
        logo_file.save(logo_path)
        audio_file.save(audio_path)

        output_filename = f"logo_audio_{video_file.filename}"
        output_path = os.path.join('static/uploads/logo_audio', output_filename)

        add_logo_and_background_audio(video_path, logo_path, audio_path, output_path)

        return send_file(output_path, as_attachment=True, download_name=output_filename)

    return render_template('add_logo_audio.html', video=None)
