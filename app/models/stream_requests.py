import sqlite3
from datetime import datetime
from .user import get_db

def create_stream_request(app, user_id):
    """Create a new stream request for a user."""
    with get_db(app) as conn:
        conn.execute('INSERT INTO stream_requests (user_id, status, requested_at) VALUES (?, ?, ?)',
                    (user_id, 'pending', datetime.now().isoformat()))
        conn.commit()

def get_pending_requests(app):
    """Retrieve all pending stream requests."""
    with get_db(app) as conn:
        requests = conn.execute('SELECT sr.id, sr.user_id, u.username, sr.requested_at FROM stream_requests sr JOIN users u ON sr.user_id = u.id WHERE sr.status = "pending" ORDER BY sr.requested_at DESC').fetchall()
        return [{'id': row['id'], 'user_id': row['user_id'], 'username': row['username'], 'requested_at': row['requested_at']} for row in requests]

def update_stream_request(app, request_id, status):
    """Update the status of a stream request (accepted or rejected)."""
    with get_db(app) as conn:
        conn.execute('UPDATE stream_requests SET status = ? WHERE id = ?', (status, request_id))
        conn.commit()
