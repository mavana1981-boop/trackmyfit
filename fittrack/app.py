from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
import os
import logging

log = logging.getLogger(__name__)

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()

_db_initialized = False


def _get_db_url():
    url = os.environ.get('DATABASE_URL', 'postgresql://localhost/fittrack')
    # Railway emits postgres:// — SQLAlchemy 2.x requires postgresql://
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    app.config['SQLALCHEMY_DATABASE_URI'] = _get_db_url()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Faça login para continuar.'
    login_manager.login_message_category = 'info'

    from routes.auth import auth_bp
    from routes.main import main_bp
    from routes.exercises import exercises_bp
    from routes.workouts import workouts_bp
    from routes.history import history_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(exercises_bp)
    app.register_blueprint(workouts_bp)
    app.register_blueprint(history_bp)

    @app.before_request
    def init_db_once():
        """
        Lazy DB init: runs on the very first request the worker receives.
        By then Railway has the DB service up and DATABASE_URL injected.
        Uses a module-level flag so it only runs once per worker process.
        """
        global _db_initialized
        if _db_initialized:
            return
        try:
            from models import seed_data
            db.create_all()
            seed_data()
            _db_initialized = True
            log.info('DB initialised successfully.')
        except Exception as exc:
            # Log but don't crash — next request will retry.
            log.error('DB init error (will retry): %s', exc)

    return app


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    app.run(debug=True)
