import sqlite3
from src.config import settings


def _db():
    conn = sqlite3.connect(settings.business_db)
    conn.row_factory = sqlite3.Row
    return conn