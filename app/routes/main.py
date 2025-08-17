from flask import Blueprint, render_template, session, current_app, redirect, url_for, flash
from flask_socketio import emit, join_room, leave_room
from ..models.user import get_db
from ..models.analytics import log_viewer_count
from .auth import login_required, admin_required
from datetime import datetime
from ..routes.api import stats
import os

main_bp = Blueprint('main', __name__)

connected_users = []

@main_bp.route('/')
def index():
    return render_template('index.html', stats=stats)

@main_bp.route('/stream')
@login_required
def stream():
    user_id = session['user_id']
    with get_db(current_app) as conn:
        request = conn.execute('SELECT status FROM stream_requests WHERE user_id = ? ORDER BY requested_at DESC LIMIT 1', (user_id,)).fetchone()
        if request:
            if request['status'] == 'accepted':
                stats['viewers'] += 1
                stats['total_views'] += 1
                log_viewer_count(current_app, stats['viewers'])
                user = conn.execute('SELECT username, email FROM users WHERE id = ?', (user_id,)).fetchone()
                connected_users.append({'id': user_id, 'username': user['username'], 'email': user['email']})
                from app import socketio
                socketio.emit('update_users', connected_users, to=None)
                return render_template('stream.html', user=session, stats=stats)
            elif request['status'] == 'rejected':
                flash('Votre demande pour rejoindre le live a été refusée.', 'error')
                return redirect(url_for('main.index'))
            else:
                flash('Votre demande pour rejoindre le live est en attente de validation.', 'info')
                return redirect(url_for('main.index'))
        else:
            conn.execute('INSERT INTO stream_requests (user_id, status, requested_at) VALUES (?, ?, ?)',
                        (user_id, 'pending', datetime.now().isoformat()))
            conn.commit()
            flash('Votre demande pour rejoindre le live a été envoyée à l\'administrateur.', 'info')
            user = conn.execute('SELECT username, email FROM users WHERE id = ?', (user_id,)).fetchone()
            from app import socketio
            socketio.emit('new_request', {
                'user_id': user_id,
                'username': user['username'],
                'email': user['email'],
                'requested_at': datetime.now().isoformat()
            }, to='admin_room')
            return redirect(url_for('main.index'))

@main_bp.route('/admin')
@admin_required
def admin():
    uploaded_videos = [f for f in os.listdir(current_app.config['UPLOAD_FOLDER']) if f.endswith(('.mp4', '.avi', '.mkv'))]
    return render_template('admin.html', stats=stats, uploaded_videos=uploaded_videos)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    with get_db(current_app) as conn:
        total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        total_admins = conn.execute('SELECT COUNT(*) FROM users WHERE role = ?', ('admin',)).fetchone()[0]
        recent_logins = conn.execute('SELECT username, last_login, email FROM users ORDER BY last_login DESC LIMIT 5').fetchall()
        total_watch_time = conn.execute('SELECT SUM(viewers) FROM analytics WHERE type = ?', ('hourly',)).fetchone()[0] or 0
        notifications = conn.execute('SELECT id, message, created_at, read FROM notifications WHERE user_id = ? ORDER BY created_at DESC', (session['user_id'],)).fetchall()
    dashboard_stats = {
        'total_users': total_users,
        'total_admins': total_admins,
        'recent_logins': [(row['username'], row['last_login'], row['email']) for row in recent_logins],
        'total_watch_time': total_watch_time,
        'notifications': [{'id': row['id'], 'message': row['message'], 'created_at': row['created_at'], 'read': row['read']} for row in notifications]
    }
    return render_template('dashboard.html', user=session, stats=stats, dashboard_stats=dashboard_stats, connected_users=connected_users)

@main_bp.route('/manage_users')
@admin_required
def manage_users():
    with get_db(current_app) as conn:
        users = conn.execute('SELECT id, username, email, role, created_at, last_login, active FROM users').fetchall()
        requests = conn.execute('SELECT sr.id, sr.user_id, sr.status, sr.requested_at, u.username, u.email FROM stream_requests sr JOIN users u ON sr.user_id = u.id WHERE sr.status = ?', ('pending',)).fetchall()
    return render_template('users.html', users=users, requests=requests)

@main_bp.route('/manage_request/<int:request_id>/<action>', methods=['POST'])
@admin_required
def manage_request(request_id, action):
    if action not in ['accept', 'reject']:
        flash('Action non valide.', 'error')
        return redirect(url_for('main.manage_users'))
    with get_db(current_app) as conn:
        request = conn.execute('SELECT user_id, status FROM stream_requests WHERE id = ?', (request_id,)).fetchone()
        if not request:
            flash('Demande non trouvée.', 'error')
            return redirect(url_for('main.manage_users'))
        if request['status'] != 'pending':
            flash('Cette demande a déjà été traitée.', 'error')
            return redirect(url_for('main.manage_users'))
        user = conn.execute('SELECT username, email FROM users WHERE id = ?', (request['user_id'],)).fetchone()
        conn.execute('UPDATE stream_requests SET status = ? WHERE id = ?', (action + 'ed', request_id))
        conn.execute('INSERT INTO notifications (user_id, message, created_at, read) VALUES (?, ?, ?, ?)',
                    (request['user_id'], f'Votre demande pour rejoindre le live a été { "acceptée" if action == "accept" else "refusée" }.',
                     datetime.now().isoformat(), 0))
        conn.commit()
        flash(f'Demande de {user["username"]} {action + "ée"}.', 'success')
        from app import socketio
        socketio.emit('request_updated', {
            'request_id': request_id,
            'status': action + 'ed',
            'username': user['username'],
            'email': user['email']
        }, to='admin_room')
    return redirect(url_for('main.manage_users'))

from app import socketio

@socketio.on('connect')
def handle_connect():
    if session.get('role') == 'admin':
        join_room('admin_room')
    if session.get('user_id'):
        join_room('stream_room')

@socketio.on('disconnect')
def handle_disconnect():
    if session.get('user_id'):
        user_id = session['user_id']
        global connected_users
        connected_users = [u for u in connected_users if u['id'] != user_id]
        if session.get('role') == 'admin':
            leave_room('admin_room')
        leave_room('stream_room')
        socketio.emit('update_users', connected_users, to=None)

@socketio.on('send_message')
def handle_message(data):
    if 'user_id' not in session:
        return
    user_id = session['user_id']
    with get_db(current_app) as conn:
        request = conn.execute('SELECT status FROM stream_requests WHERE user_id = ? ORDER BY requested_at DESC LIMIT 1', (user_id,)).fetchone()
        if not request or request['status'] != 'accepted':
            return
        message = data['message']
        if message.strip():
            conn.execute('INSERT INTO messages (user_id, message, created_at) VALUES (?, ?, ?)',
                        (user_id, message, datetime.now().isoformat()))
            conn.commit()
            user = conn.execute('SELECT username FROM users WHERE id = ?', (user_id,)).fetchone()
            socketio.emit('new_message', {
                'username': user['username'],
                'message': message,
                'created_at': datetime.now().isoformat()
            }, to='stream_room')