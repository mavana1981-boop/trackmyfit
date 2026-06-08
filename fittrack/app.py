import os
import logging
import threading
import time

log = logging.getLogger(__name__)

from flask import Flask 
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()


def _get_db_url():
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        raise RuntimeError('DATABASE_URL não configurada.')
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


def _init_db_background(app, retries=20, delay=5):
    """
    Runs in a background thread: waits for Postgres, creates tables, seeds data.
    Never crashes the main process.
    """
    for attempt in range(1, retries + 1):
        try:
            with app.app_context():
                db.create_all()
                from models import seed_data
                seed_data()
            log.info('DB initialised successfully on attempt %d.', attempt)
            return
        except Exception as exc:
            log.warning('DB init attempt %d/%d failed: %s', attempt, retries, exc)
            time.sleep(delay)
    log.error('DB init gave up after %d attempts.', retries)


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

    # Start background DB init — does NOT block gunicorn boot or healthcheck
    t = threading.Thread(target=_init_db_background, args=(app,), daemon=True)
    t.start()

    return app


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    app.run(debug=True)
