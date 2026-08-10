from flask import Flask

from app.config import Config


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    config_class.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    config_class.BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    (config_class.BOOKS_DIR / "incoming").mkdir(parents=True, exist_ok=True)
    (config_class.BOOKS_DIR / "ready").mkdir(parents=True, exist_ok=True)

    from app.main import bp

    app.register_blueprint(bp)
    return app
