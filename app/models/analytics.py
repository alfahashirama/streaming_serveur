from datetime import datetime
from .user import get_db

def log_viewer_count(app, viewers):
    with get_db(app) as conn:
        conn.execute('INSERT INTO analytics (timestamp, viewers, type) VALUES (?, ?, ?)',
                    (datetime.now().isoformat(), viewers, 'hourly'))
        conn.commit()