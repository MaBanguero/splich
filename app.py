from flask import Flask, request, render_template, redirect, url_for
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from moviepy.editor import VideoFileClip
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max file size

def cortar_video(input_video_path, duracion_segmento):
    video = VideoFileClip(input_video_path)
    duracion_total = int(video.duration)
    segments = []
    
    for start_time in range(0, duracion_total, duracion_segmento):
        end_time = min(start_time + duracion_segmento, duracion_total)
        output_filename = f"segmento_{start_time}_{end_time}.mp4"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        ffmpeg_extract_subclip(input_video_path, start_time, end_time, targetname=output_path)
        segments.append(output_path)
    
    return segments

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'video' not in request.files or 'duration' not in request.form:
            return redirect(request.url)
        
        file = request.files['video']
        duration = int(request.form['duration'])
        
        if file.filename == '' or duration <= 0:
            return redirect(request.url)
        
        if file:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            segments = cortar_video(filepath, duration)
            return render_template('index.html', segments=segments)
    
    return render_template('index.html', segments=None)

if __name__ == '__main__':
    app.run(debug=True)

