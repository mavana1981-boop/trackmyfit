from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
import os

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://localhost/fittrack')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

    with app.app_context():
        db.create_all()
        from models import seed_data
        seed_data()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
