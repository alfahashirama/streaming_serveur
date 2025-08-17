
import sqlite3
from datetime import datetime
from .user import get_db

def create_notification(app, user_id, message):
    """Create a new notification for a user."""
    with get_db(app) as conn:
        conn.execute('INSERT INTO notifications (user_id, message, created_at, read) VALUES (?, ?, ?, ?)',
                    (user_id, message, datetime.now().isoformat(), 0))
        conn.commit()

def get_user_notifications(app, user_id):
    """Retrieve all notifications for a user."""
    with get_db(app) as conn:
        notifications = conn.execute('SELECT id, message, created_at, read FROM notifications WHERE user_id = ? ORDER BY created_at DESC',
                                    (user_id,)).fetchall()
        return [{'id': row['id'], 'message': row['message'], 'created_at': row['created_at'], 'read': row['read']} for row in notifications]

def mark_notification_read(app, notification_id):
    """Mark a notification as read."""
    with get_db(app) as conn:
        conn.execute('UPDATE notifications SET read = 1 WHERE id = ?', (notification_id,))
        conn.commit()