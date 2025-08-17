from contextlib import contextmanager
import sqlite3
from flask import current_app

@contextmanager
def get_db(app):
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()