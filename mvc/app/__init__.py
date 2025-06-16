from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from mvc.app.config import Config

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    from .controller.user_controller import user_dp
    app.register_blueprint(user_dp, url_prefix='/user')

    return app