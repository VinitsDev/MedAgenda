from flask import Flask
from config import Config
from app.extensions import db, migrate, login_manager, csrf


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para acessar esta página."
    login_manager.login_message_category = "warning"

    from app import models  # noqa: F401
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.commands import registrar_comandos

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    registrar_comandos(app)

    return app