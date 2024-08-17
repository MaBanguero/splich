from flask import Flask
from config import Config
from views import main_bp, video_bp

app = Flask(__name__)
app.config.from_object(Config)

# Registrar Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(video_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
