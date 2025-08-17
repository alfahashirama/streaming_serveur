from flask import Blueprint, request, current_app, session, Response
from ..utils.camera import Camera
from ..models.analytics import log_viewer_count
from ..models.user import get_db
from .auth import admin_required, login_required
import os
import time
import logging

api_bp = Blueprint('api', __name__)

# Configuration du logging
logging.basicConfig(level=logging.DEBUG, filename='app.log', filemode='a', format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

stats = {
    'viewers': 0,
    'total_views': 0,
    'stream_active': False,
    'uptime': 0,
    'video_path': None,
    'start_time': None,
    'stream_type': None
}

@api_bp.route('/api/control_stream', methods=['POST'])
@admin_required
def control_stream():
    logger.debug(f"Requête reçue pour /api/control_stream: {request.json}")
    global stats
    action = request.json.get('action')
    stream_type = request.json.get('stream_type')
    video_path = request.json.get('video_path')

    if action not in ['start', 'stop']:
        logger.error(f"Action non valide: {action}")
        return Response('Action non valide', status=400)

    if action == 'start':
        if stats['stream_active']:
            logger.warning("Stream déjà actif")
            return Response('Stream déjà actif', status=400)
        stats['stream_active'] = True
        stats['start_time'] = time.time()
        stats['stream_type'] = stream_type
        if stream_type == 'video' and video_path:
            stats['video_path'] = video_path
        elif stream_type == 'webcam':
            stats['video_path'] = None
            try:
                Camera.get_instance().start(upload_folder=current_app.config['UPLOAD_FOLDER'])
            except Exception as e:
                logger.error(f"Erreur lors du démarrage de la webcam: {str(e)}")
                return Response('Erreur lors du démarrage de la webcam', status=500)
        log_viewer_count(current_app, stats['viewers'])
        logger.info("Stream démarré")
        return Response(status=204)

    if action == 'stop':
        if not stats['stream_active']:
            logger.warning("Aucun stream actif")
            return Response('Aucun stream actif', status=400)
        stats['stream_active'] = False
        stats['viewers'] = 0
        stats['start_time'] = None
        stats['stream_type'] = None
        stats['video_path'] = None
        Camera.get_instance().stop()
        log_viewer_count(current_app, stats['viewers'])
        logger.info("Stream arrêté")
        return Response(status=204)

@api_bp.route('/api/upload', methods=['POST'])
@admin_required
def upload():
    logger.debug("Requête reçue pour /api/upload")
    if 'file' not in request.files:
        logger.error("Aucun fichier fourni")
        return Response('Aucun fichier fourni', status=400)
    file = request.files['file']
    if file.filename == '':
        logger.error("Aucun fichier sélectionné")
        return Response('Aucun fichier sélectionné', status=400)
    if file and file.filename.endswith(('.mp4', '.avi', '.mkv')):
        filename = f"{int(time.time())}_{file.filename}"
        file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
        logger.info(f"Fichier uploadé: {filename}")
        return Response(status=204)
    logger.error("Format de fichier non supporté")
    return Response('Format de fichier non supporté', status=400)

@api_bp.route('/api/stream')
def stream():
    if not stats['stream_active'] or stats['stream_type'] != 'webcam':
        logger.error("Aucun stream webcam actif")
        return Response('Aucun stream webcam actif', status=400)
    return Response(Camera.get_instance().gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@api_bp.route('/api/videos', methods=['GET'])
@admin_required
def list_videos():
    logger.debug("Requête reçue pour /api/videos")
    upload_folder = current_app.config['UPLOAD_FOLDER']
    videos = [f for f in os.listdir(upload_folder) if f.endswith(('.mp4', '.avi', '.mkv'))]
    logger.info(f"Vidéos récupérées: {videos}")
    return jsonify({'videos': videos}), 200

@api_bp.route('/api/notifications/<int:notification_id>/<action>', methods=['POST'])
@login_required
def manage_notification(notification_id, action):
    logger.debug(f"Requête reçue pour /api/notifications/{notification_id}/{action}, user_id={session['user_id']}")
    from ..models.notifications import mark_notification_read
    if action not in ['read', 'delete']:
        logger.error(f"Action non valide: {action}")
        return Response('Action non valide', status=400)
    with get_db(current_app) as conn:
        notification = conn.execute('SELECT id, user_id, message, read, created_at FROM notifications WHERE id = ?', (notification_id,)).fetchone()
        logger.debug(f"Notification trouvée: {dict(notification) if notification else None}")
        if not notification:
            logger.error(f"Notification ID {notification_id} non trouvée")
            return Response('Notification non trouvée', status=404)
        if notification['user_id'] != session['user_id']:
            logger.error(f"Accès non autorisé: user_id={session['user_id']} tente d'accéder à notification_id={notification_id}")
            return Response('Accès non autorisé', status=403)
        if action == 'read':
            if notification['read']:
                logger.warning(f"Notification {notification_id} déjà lue")
                return Response('Notification déjà lue', status=400)
            mark_notification_read(current_app, notification_id)
            logger.info(f"Notification {notification_id} marquée comme lue")
        elif action == 'delete':
            conn.execute('DELETE FROM notifications WHERE id = ?', (notification_id,))
            conn.commit()
            logger.info(f"Notification {notification_id} supprimée")
    from .. import socketio
    socketio.emit('notification_updated', {'notification_id': notification_id, 'action': action}, to=str(session['user_id']))
    logger.debug(f"Événement SocketIO 'notification_updated' émis pour notification_id={notification_id}, action={action}")
    return Response(status=204)

@api_bp.route('/api/control_recording', methods=['POST'])
@admin_required
def control_recording():
    logger.debug(f"Requête reçue pour /api/control_recording: {request.json}")
    action = request.json.get('action')
    if action not in ['start', 'stop']:
        logger.error(f"Action non valide: {action}")
        return Response('Action non valide', status=400)
    camera = Camera.get_instance()
    if action == 'start':
        if camera.recording:
            logger.warning("Enregistrement déjà en cours")
            return Response('Enregistrement déjà en cours', status=400)
        if camera.start_recording():
            logger.info("Enregistrement démarré")
            return Response(status=204)
        logger.error("Impossible de démarrer l'enregistrement")
        return Response('Impossible de démarrer l\'enregistrement', status=500)
    if action == 'stop':
        if not camera.recording:
            logger.warning("Aucun enregistrement en cours")
            return Response('Aucun enregistrement en cours', status=400)
        camera.stop_recording()
        logger.info("Enregistrement arrêté")
        return Response(status=204)

@api_bp.route('/api/promote_user/<int:user_id>', methods=['POST'])
@admin_required
def promote_user(user_id):
    logger.debug(f"Tentative de promotion de l'utilisateur ID {user_id}")
    with get_db(current_app) as conn:
        user = conn.execute('SELECT username, role FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            logger.error(f"Utilisateur ID {user_id} non trouvé")
            return Response('Utilisateur non trouvé', status=404)
        if user['role'] == 'admin':
            logger.warning(f"L'utilisateur ID {user_id} est déjà administrateur")
            return Response('Utilisateur déjà administrateur', status=400)
        conn.execute('UPDATE users SET role = ? WHERE id = ?', ('admin', user_id))
        conn.commit()
        logger.info(f"Utilisateur {user['username']} (ID {user_id}) promu administrateur")
    from .. import socketio
    socketio.emit('user_promoted', {'user_id': user_id, 'username': user['username']}, to='admin_room')
    logger.debug(f"Événement SocketIO 'user_promoted' émis pour user_id={user_id}")
    return Response(status=204)