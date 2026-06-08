<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FitTrack — Cadastro</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root { --coral: #E8623A; --coral-dark: #C44E2A; --coral-pale: #FFF0EC; --dark: #1A1A1A; --border: #EBEBEB; }
        body { font-family: 'DM Sans', sans-serif; background: #F7F5F3; min-height: 100vh; }
        .topbar { background: var(--coral); color: white; padding: 16px 20px; display: flex; align-items: center; gap: 12px; }
        .topbar a { color: white; text-decoration: none; font-size: 1.3rem; }
        .topbar h1 { font-family: 'Syne', sans-serif; font-size: 1.2rem; font-weight: 800; }
        .form-wrap { padding: 24px 20px; max-width: 420px; margin: 0 auto; }
        .form-group { margin-bottom: 16px; }
        .form-label { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 0.82rem; color: #555; display: block; margin-bottom: 6px; text-transform: uppercase; }
        .form-control { width: 100%; padding: 14px 16px; border: 1.5px solid var(--border); border-radius: 14px; font-family: 'DM Sans', sans-serif; font-size: 1rem; color: var(--dark); background: white; outline: none; transition: border-color 0.15s; }
        .form-control:focus { border-color: var(--coral); }
        .btn-coral { width: 100%; padding: 15px; border-radius: 14px; background: var(--coral); color: white; font-family: 'Syne', sans-serif; font-size: 1rem; font-weight: 800; border: none; cursor: pointer; }
        .btn-coral:hover { background: var(--coral-dark); }
        .footer-link { text-align: center; margin-top: 20px; font-size: 0.9rem; color: #888; }
        .footer-link a { color: var(--coral); font-weight: 600; text-decoration: none; }
        .alert { padding: 12px 16px; border-radius: 12px; font-size: 0.9rem; margin-bottom: 16px; }
        .alert-error { background: #FEE; color: #E74C3C; border: 1px solid #FCC; }
        .alert-success { background: #EFFFEF; color: #27AE60; }
    </style>
</head>
<body>
    <div class="topbar">
        <a href="{{ url_for('auth.login') }}">←</a>
        <h1>Criar Conta</h1>
    </div>
    <div class="form-wrap">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}{% for cat, msg in messages %}<div class="alert alert-{{ cat }}">{{ msg }}</div>{% endfor %}{% endif %}
        {% endwith %}
        <form method="POST">
            <div class="form-group">
                <label class="form-label">Nome</label>
                <input type="text" name="name" class="form-control" placeholder="Seu nome" required autofocus>
            </div>
            <div class="form-group">
                <label class="form-label">E-mail</label>
                <input type="email" name="email" class="form-control" placeholder="seu@email.com" required>
            </div>
            <div class="form-group">
                <label class="form-label">Senha</label>
                <input type="password" name="password" class="form-control" placeholder="Mínimo 6 caracteres" required>
            </div>
            <div class="form-group">
                <label class="form-label">Confirmar Senha</label>
                <input type="password" name="confirm_password" class="form-control" placeholder="Repita a senha" required>
            </div>
            <button type="submit" class="btn-coral">Criar Conta</button>
        </form>
        <div class="footer-link">
            Já tem conta? <a href="{{ url_for('auth.login') }}">Entrar</a>
        </div>
    </div>
</body>
</html>
