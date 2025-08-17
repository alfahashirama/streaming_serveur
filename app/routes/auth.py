from flask import Blueprint, render_template, session, request, redirect, url_for, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from ..models.user import get_db
from datetime import datetime
import requests

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Veuillez vous connecter pour accéder à cette page.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Accès réservé aux administrateurs.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def verify_recaptcha(response_token):
    """Vérifie la réponse reCAPTCHA auprès de l'API de Google."""
    secret_key = current_app.config['RECAPTCHA_SECRET_KEY']
    payload = {
        'secret': secret_key,
        'response': response_token
    }
    response = requests.post('https://www.google.com/recaptcha/api/siteverify', data=payload)
    result = response.json()
    return result.get('success', False)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        recaptcha_response = request.form.get('g-recaptcha-response')
        if not recaptcha_response:
            flash('Veuillez compléter le CAPTCHA.', 'error')
            return redirect(url_for('auth.login'))
        if not verify_recaptcha(recaptcha_response):
            flash('Échec de la vérification CAPTCHA.', 'error')
            return redirect(url_for('auth.login'))

        username = request.form['username']
        password = request.form['password']
        with get_db(current_app) as conn:
            user = conn.execute('SELECT * FROM users WHERE username = ? AND active = 1', (username,)).fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            with get_db(current_app) as conn:
                conn.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now().isoformat(), user['id']))
                conn.commit()
            flash('Connexion réussie !', 'success')
            return redirect(url_for('main.dashboard' if user['role'] == 'admin' else 'main.index'))
        flash('Nom d’utilisateur ou mot de passe incorrect.', 'error')
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        recaptcha_response = request.form.get('g-recaptcha-response')
        if not recaptcha_response:
            flash('Veuillez compléter le CAPTCHA.', 'error')
            return redirect(url_for('auth.register'))
        if not verify_recaptcha(recaptcha_response):
            flash('Échec de la vérification CAPTCHA.', 'error')
            return redirect(url_for('auth.register'))

        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Les mots de passe ne correspondent pas.', 'error')
            return redirect(url_for('auth.register'))
        if len(password) < 6:
            flash('Le mot de passe doit contenir au moins 6 caractères.', 'error')
            return redirect(url_for('auth.register'))
        with get_db(current_app) as conn:
            try:
                conn.execute('INSERT INTO users (username, email, password, role, created_at, active) VALUES (?, ?, ?, ?, ?, ?)',
                            (username, email, generate_password_hash(password), 'viewer', datetime.now().isoformat(), 1))
                conn.commit()
                flash('Inscription réussie ! Veuillez vous connecter.', 'success')
                return redirect(url_for('auth.login'))
            except sqlite3.IntegrityError:
                flash('Nom d’utilisateur ou email déjà utilisé.', 'error')
    return render_template('register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Vous avez été déconnecté.', 'success')
    return redirect(url_for('auth.login'))