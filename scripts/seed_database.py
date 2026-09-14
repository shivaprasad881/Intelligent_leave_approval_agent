"""Seed the demo business database with customer operations and HR data.

Run:
    python -m scripts.seed_database
"""
import sqlite3
from pathlib import Path

from src.config import settings

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    department TEXT NOT NULL,
    designation TEXT NOT NULL,
    manager_name TEXT,
    employment_type TEXT NOT NULL,
    join_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive','terminated')),
    annual_leave_balance REAL NOT NULL DEFAULT 0,
    sick_leave_balance REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employees(employee_id),
    leave_type TEXT NOT NULL CHECK(leave_type IN ('annual','sick','unpaid','other')),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    days REAL NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','cancelled')),
    approver_note TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_leave_employee_id ON leave_requests(employee_id);
CREATE INDEX IF NOT EXISTS idx_leave_status ON leave_requests(status);
"""


EMPLOYEES = [
    ("EMP001", "Ananya Rao", "ananya.rao@intellidesk.example", "Engineering",
     "Software Engineer", "Vikram Mehta", "full_time", "2023-06-12", "active", 14.0, 8.0),
    ("EMP002", "Rahul Verma", "rahul.verma@intellidesk.example", "Sales",
     "Account Manager", "Neha Kapoor", "full_time", "2022-11-01", "active", 10.0, 11.0),
    ("EMP003", "Meera Iyer", "meera.iyer@intellidesk.example", "Human Resources",
     "HR Executive", "Sonal Shah", "full_time", "2024-02-19", "active", 18.0, 9.0),
    ("EMP004", "Arjun Nair", "arjun.nair@intellidesk.example", "Support",
     "Support Specialist", "Farah Khan", "contract", "2025-01-06", "active", 7.0, 5.0),
    ("EMP005", "Kavya Reddy", "kavya.reddy@intellidesk.example", "Finance",
     "Financial Analyst", "Rohit Sen", "full_time", "2021-08-23", "active", 21.0, 12.0),
]

LEAVE_REQUESTS = [
    (5001, "EMP001", "annual", "2026-06-10", "2026-06-12", 3.0,
     "Family function", "approved", "Approved by manager", "2026-05-25T10:00:00+00:00"),
    (5002, "EMP002", "sick", "2026-07-14", "2026-07-15", 2.0,
     "Viral fever", "approved", "Medical note not required for two days", "2026-07-14T08:30:00+00:00"),
    (5003, "EMP004", "annual", "2026-08-03", "2026-08-07", 5.0,
     "Personal travel", "pending", "", "2026-07-16T06:00:00+00:00"),
]


def main() -> None:
    Path(settings.business_db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.business_db)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA)

    conn.executemany(
        "INSERT OR REPLACE INTO employees VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        EMPLOYEES,
    )
    conn.executemany(
        "INSERT OR REPLACE INTO leave_requests VALUES (?,?,?,?,?,?,?,?,?,?)",
        LEAVE_REQUESTS,
    )
    conn.commit()
    conn.close()
    print(f"Seeded {len(EMPLOYEES)} employees into {settings.business_db}")


if __name__ == "__main__":
    main()