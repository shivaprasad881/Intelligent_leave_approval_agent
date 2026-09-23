import sqlite3
from typing import List, Optional, Dict


class CalendarRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # 1. Fetch all records
    def get_all(self) -> List[Dict]:
        conn = self._connect()
        try:
            cur = conn.execute("SELECT date, isblacklisted FROM calendar")
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    # 2. Fetch one record by date
    def get_by_date(self, date: str) -> Optional[Dict]:
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT date, isblacklisted FROM calendar WHERE date = ?",
                (date,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_flag(self, date: str, new_flag: int) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE calendar SET isblacklisted = ? WHERE date = ?",
                (new_flag, date)
            )
            conn.commit()
        finally:
            conn.close()