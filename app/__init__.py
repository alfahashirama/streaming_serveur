import os
import sqlite3
from flask import Flask
from flask_socketio import SocketIO
from .config import Config
import logging
from logging.handlers import RotatingFileHandler

socketio = SocketIO()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.instance_path, 'logs'), exist_ok=True)

    handler = RotatingFileHandler(os.path.join(app.instance_path, 'logs', 'app.log'), maxBytes=10000, backupCount=1)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)

    socketio.init_app(app)

    with app.app_context():
        db_path = app.config['DATABASE']
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login TEXT,
            active INTEGER NOT NULL
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            viewers INTEGER NOT NULL,
            type TEXT NOT NULL
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS stream_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            requested_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            read INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        cursor = conn.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('admin',))
        if cursor.fetchone()[0] == 0:
            from werkzeug.security import generate_password_hash
            from datetime import datetime
            conn.execute('INSERT INTO users (username, email, password, role, created_at, active) VALUES (?, ?, ?, ?, ?, ?)',
                         ('admin', 'admin@example.com', generate_password_hash('admin123'), 'admin', datetime.now().isoformat(), 1))
        conn.commit()
        conn.close()

    from .routes.main import main_bp
    from .routes.auth import auth_bp
    from .routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)

    return app