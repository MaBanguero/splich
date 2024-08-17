from flask import send_file, abort
import os
from . import video_bp

@video_bp.route('/download/<folder>/<filename>')
def download(folder, filename):
    file_path = os.path.join('static/uploads', folder, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=filename)
    else:
        abort(404)
