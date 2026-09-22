from src.db import _db


def get_by_id(empid: str):
    with _db() as conn:
        return conn.execute(
            "SELECT * FROM employees WHERE employee_id = ?", (empid,)
        ).fetchone()