from flask import render_template, request, redirect, send_file
import os
from modules.audio_processing import text_to_speech
from . import video_bp

@video_bp.route('/text_to_speech', methods=['GET', 'POST'])
def text_to_speech_view():
    if request.method == 'POST':
        text = request.form.get('text')
        if not text:
            return redirect(request.url)

        tts_output_path = os.path.join('static/uploads/tts', 'tts_output.wav')

        duplicated_voice_path = None  # Si tienes un path guardado para voz duplicada
        text_to_speech(text, tts_output_path, duplicated_voice_path)

        return send_file(tts_output_path, as_attachment=True, download_name='tts_output.wav')

    return render_template('text_to_speech.html')
