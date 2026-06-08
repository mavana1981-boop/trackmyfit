from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        flash('E-mail ou senha incorretos.', 'error')
    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if not name or not email or not password:
            flash('Preencha todos os campos.', 'error')
        elif password != confirm:
            flash('As senhas não coincidem.', 'error')
        elif len(password) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('Este e-mail já está cadastrado.', 'error')
        else:
            hashed = bcrypt.generate_password_hash(password).decode('utf-8')
            user = User(name=name, email=email, password=hashed)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(f'Bem-vindo, {name}! Conta criada com sucesso.', 'success')
            return redirect(url_for('main.dashboard'))
    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
