from flask import render_template, request, redirect, send_file
import os
from modules.audio_processing import duplicate_voice
from . import video_bp

@video_bp.route('/duplicate_voice', methods=['GET', 'POST'])
def duplicate_voice_view():
    if request.method == 'POST':
        if 'audio' not in request.files:
            return redirect(request.url)

        file = request.files['audio']

        if file.filename == '':
            return redirect(request.url)

        filepath = os.path.join('static/uploads/duplicate_voice', file.filename)
        file.save(filepath)

        duplicated_voice_path = os.path.join('static/uploads/duplicate_voice', 'duplicated_' + file.filename)
        duplicate_voice(filepath, duplicated_voice_path)

        return send_file(duplicated_voice_path, as_attachment=True, download_name='duplicated_' + file.filename)

    return render_template('duplicate_voice.html')
