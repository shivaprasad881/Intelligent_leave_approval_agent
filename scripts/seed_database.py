"""Seed the demo business database with customer operations and HR data.

Run:
    python -m scripts.seed_database
"""
import sqlite3
from pathlib import Path

from src.config import settings

SCHEMA = """

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY,
    employee_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    department TEXT NOT NULL,
    designation TEXT NOT NULL,
    manager_name TEXT,
    employment_type TEXT NOT NULL,
    join_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    annual_leave_balance REAL NOT NULL DEFAULT 0,
    sick_leave_balance REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS leave_requests (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    leave_type TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    days REAL NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    approver_note TEXT,
    created_at TEXT NOT NULL
);
"""









EMPLOYEES = [
    (1, "EMP001", "Ananya Rao", "ananya.rao@intellidesk.example", "Engineering",
     "Software Engineer", "Vikram Mehta", "full_time", "2023-06-12", "active", 14.0, 8.0),
    (2, "EMP002", "Rahul Verma", "rahul.verma@intellidesk.example", "Sales",
     "Account Manager", "Neha Kapoor", "full_time", "2022-11-01", "active", 10.0, 11.0),
    (3, "EMP003", "Meera Iyer", "meera.iyer@intellidesk.example", "Human Resources",
     "HR Executive", "Sonal Shah", "full_time", "2024-02-19", "active", 18.0, 9.0),
    (4, "EMP004", "Arjun Nair", "arjun.nair@intellidesk.example", "Support",
     "Support Specialist", "Farah Khan", "contract", "2025-01-06", "active", 7.0, 5.0),
    (5, "EMP005", "Kavya Reddy", "kavya.reddy@intellidesk.example", "Finance",
     "Financial Analyst", "Rohit Sen", "full_time", "2021-08-23", "active", 21.0, 12.0),
]

LEAVE_REQUESTS = [
    (5001, 1, "annual", "2026-06-10", "2026-06-12", 3.0,
     "Family function", "approved", "Approved by manager", "2026-05-25T10:00:00+00:00"),
    (5002, 2, "sick", "2026-07-14", "2026-07-15", 2.0,
     "Viral fever", "approved", "Medical note not required for two days", "2026-07-14T08:30:00+00:00"),
    (5003, 4, "annual", "2026-08-03", "2026-08-07", 5.0,
     "Personal travel", "pending", "", "2026-07-16T06:00:00+00:00"),
]


def main() -> None:
    Path(settings.business_db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.business_db)
    conn.executescript(SCHEMA)
    
    conn.executemany("INSERT OR REPLACE INTO employees VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", EMPLOYEES)
    conn.executemany("INSERT OR REPLACE INTO leave_requests VALUES (?,?,?,?,?,?,?,?,?,?)", LEAVE_REQUESTS)
    conn.commit()
    conn.close()
    print(f"Seeded  5 employees into {settings.business_db}")


if __name__ == "__main__":
    main()

# conn.executemany("INSERT OR REPLACE INTO customers VALUES (?,?,?,?,?,?)", CUSTOMERS)
#     conn.executemany("INSERT OR REPLACE INTO orders VALUES (?,?,?,?,?,?)", ORDERS)
#     conn.executemany("INSERT OR REPLACE INTO tickets VALUES (?,?,?,?,?,?,?,?)", TICKETS)
#     conn.executemany("INSERT OR REPLACE INTO inventory VALUES (?,?,?,?,?)", INVENTORY)

# CREATE TABLE IF NOT EXISTS customers (
#     id INTEGER PRIMARY KEY,
#     name TEXT NOT NULL,
#     email TEXT UNIQUE NOT NULL,
#     tier TEXT DEFAULT 'standard',
#     signup_date TEXT,
#     lifetime_value_usd REAL DEFAULT 0
# );
# CREATE TABLE IF NOT EXISTS orders (
#     id INTEGER PRIMARY KEY,
#     customer_id INTEGER REFERENCES customers(id),
#     order_date TEXT,
#     status TEXT,
#     total_usd REAL,
#     items TEXT
# );
# CREATE TABLE IF NOT EXISTS tickets (
#     id INTEGER PRIMARY KEY,
#     customer_id INTEGER REFERENCES customers(id),
#     subject TEXT,
#     description TEXT,
#     priority TEXT,
#     status TEXT,
#     created_at TEXT,
#     last_note TEXT
# );
# CREATE TABLE IF NOT EXISTS inventory (
#     sku TEXT PRIMARY KEY,
#     product_name TEXT,
#     stock_qty INTEGER,
#     warehouse TEXT,
#     unit_price_usd REAL
# );


# CUSTOMERS = [
#     (1, "Aarav Sharma", "aarav@acmecorp.com", "enterprise", "2023-04-12", 48200.00),
#     (2, "Priya Patel", "priya.p@gmail.com", "gold", "2024-01-30", 3120.50),
#     (3, "Daniel Okafor", "d.okafor@nova.io", "standard", "2025-06-02", 410.00),
#     (4, "Mei Lin", "mei.lin@zentech.co", "gold", "2024-09-18", 5980.75),
# ]

# ORDERS = [
#     (101, 1, "2026-06-20", "delivered", 1299.00, "ProBook X1 Laptop x1"),
#     (102, 1, "2026-07-01", "shipped", 189.99, "DockStation Pro x1"),
#     (103, 2, "2026-07-08", "pending", 79.98, "ErgoMouse M3 x2"),
#     (104, 3, "2026-05-15", "returned", 249.00, "4K Monitor 27in x1"),
#     (105, 4, "2026-07-10", "delivered", 649.00, "ErgoChair V2 x1"),
# ]

# TICKETS = [
#     (9001, 2, "Order stuck in pending", "Order 103 hasn't shipped after 5 days.",
#      "normal", "open", "2026-07-13T09:15:00+00:00", ""),
# ]

# INVENTORY = [
#     ("LPT-X1-16", "ProBook X1 Laptop 16GB", 42, "WH-East", 1299.00),
#     ("DCK-PRO-2", "DockStation Pro", 130, "WH-East", 189.99),
#     ("MSE-M3-BLK", "ErgoMouse M3", 0, "WH-West", 39.99),
#     ("MON-4K-27", "4K Monitor 27in", 17, "WH-West", 249.00),
#     ("CHR-V2-GRY", "ErgoChair V2", 8, "WH-East", 649.00),
# ]

