from flask import Blueprint

main_bp = Blueprint('main', __name__)
video_bp = Blueprint('video', __name__)

from . import home, segment, randomize, process_multiple, duplicate_voice, text_to_speech, add_logo_audio, video_views
