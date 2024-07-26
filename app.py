import os
from flask import Flask, request, render_template, redirect, url_for, send_file, abort
from moviepy.editor import VideoFileClip, concatenate_videoclips
import random

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max file size

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def cortar_video(input_video_path, duracion_segmento, inicio_path=None, final_path=None):
    video = VideoFileClip(input_video_path)
    duracion_total = int(video.duration)
    segments = []

    inicio_clip = VideoFileClip(inicio_path) if inicio_path else None
    final_clip = VideoFileClip(final_path) if final_path else None

    for start_time in range(0, duracion_total, duracion_segmento):
        end_time = min(start_time + duracion_segmento, duracion_total)
        clip = video.subclip(start_time, end_time)
        if inicio_clip and final_clip:
            combined_clip = concatenate_videoclips([inicio_clip, clip, final_clip])
        elif inicio_clip:
            combined_clip = concatenate_videoclips([inicio_clip, clip])
        elif final_clip:
            combined_clip = concatenate_videoclips([clip, final_clip])
        else:
            combined_clip = clip
        
        output_filename = f"segmento_{start_time}_{end_time}.mp4"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
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
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
    video_final.write_videofile(output_path, codec='libx264', audio_codec='aac')

    return output_filename

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'video' not in request.files or 'duration' not in request.form:
            return redirect(request.url)

        file = request.files['video']
        inicio_file = request.files.get('inicio')
        final_file = request.files.get('final')
        duration = int(request.form['duration'])

        if file.filename == '' or duration <= 0:
            return redirect(request.url)

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        inicio_path = None
        final_path = None

        if inicio_file and inicio_file.filename != '':
            inicio_path = os.path.join(app.config['UPLOAD_FOLDER'], inicio_file.filename)
            inicio_file.save(inicio_path)

        if final_file and final_file.filename != '':
            final_path = os.path.join(app.config['UPLOAD_FOLDER'], final_file.filename)
            final_file.save(final_path)

        segments = cortar_video(filepath, duration, inicio_path, final_path)
        return render_template('index.html', segments=segments)

    return render_template('index.html', segments=None)

@app.route('/randomize', methods=['GET', 'POST'])
def randomize():
    if request.method == 'POST':
        if 'video' not in request.files or 'duration' not in request.form:
            return redirect(request.url)

        file = request.files['video']
        duration = int(request.form['duration'])

        if file.filename == '' or duration <= 0:
            return redirect(request.url)

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        mixed_video_filename = cortar_y_mezclar_video(filepath, duration)
        return render_template('randomize.html', video=mixed_video_filename)

    return render_template('randomize.html', video=None)

@app.route('/download/<filename>')
def download(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=filename)
    else:
        abort(404)

if __name__ == '__main__':
    app.run(debug=True)
