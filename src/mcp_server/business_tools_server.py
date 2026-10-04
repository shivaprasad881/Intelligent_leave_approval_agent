"""MCP Server — Business Operations Tools.

This is a standalone Model Context Protocol server (FastMCP) that exposes
the company's *operational systems* to any MCP-compatible client — our
LangChain agent, Claude Desktop, an IDE, another team's agent, etc.

Why MCP instead of hard-coding LangChain tools?
  * Decoupling  — the tool server owns DB credentials; the agent never does.
  * Reusability — one server, many AI clients, zero duplicated integrations.
  * Governance  — every tool call crosses a single auditable boundary.

Tools exposed:
  lookup_employee, get_employee_count, get_leave_balance,
  list_employee_leave_requests, create_leave_request,
  update_leave_request_status, get_department_summary

Run standalone (stdio transport — what the agent spawns):
    python -m src.mcp_server.business_tools_server
"""
from __future__ import annotations

from src.repositories.calendar_repository import CalendarRepository

import json
import sqlite3
from datetime import datetime, timezone
from datetime import datetime, timedelta

from mcp.server.fastmcp import FastMCP

from src.config import settings

mcp = FastMCP("business-operations")

calendar_repo = CalendarRepository("storage/business.db")


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.business_db)
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_json(rows) -> str:
    return json.dumps([dict(r) for r in rows], indent=2, default=str)



# ---------------------------------------------------------------------------
# HR / employee tools
# ---------------------------------------------------------------------------
@mcp.tool()
def lookup_employee(employee_id: str = "") -> str:
    """Find EXACTLY ONE employee by employee_id.
        Do not call this in a loop or for bulk/list lookups — not supported."""
    if not employee_id:
        return "ERROR: provide employee_id."

    with _db() as conn:
        rows = conn.execute(
            "SELECT * FROM employees WHERE employee_id = ?", (employee_id,)
        ).fetchall()

    return _rows_to_json(rows) if rows else "NOT_FOUND: no matching employee."


@mcp.tool()
def get_leave_balance(employee_id: str) -> str:
    """Return an employee's current annual and sick leave balances."""
    with _db() as conn:
        row = conn.execute(
            """SELECT employee_id, name, annual_leave_balance,
                      sick_leave_balance
               FROM employees WHERE employee_id = ?""",
            (employee_id,),
        ).fetchone()
    return _rows_to_json([row]) if row else "NOT_FOUND: employee does not exist."


@mcp.tool()
def list_employee_leave_requests(employee_id: str, limit: int = 10) -> str:
    """List an employee's recent leave requests and their approval status."""
    with _db() as conn:
        rows = conn.execute(
            """SELECT id, leave_type, start_date, end_date, days, reason,
                      status, approver_note, created_at
               FROM leave_requests
               WHERE employee_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (employee_id, limit),
        ).fetchall()
    return _rows_to_json(rows) if rows else "NOT_FOUND: no leave requests."


@mcp.tool()
def create_leave_request(empid: str, start_date: str, end_date: str, noofdays: float, reason: str, leave_type: str) -> str:
    """
        Creates a leave request for the employee after validating inputs,
        checking employee existence, leave type, leave balance, pending
        requests, and blacklisted dates. On success, deducts the requested
        days from the employee's specific leave balance.
    """

    # 1. Validate inputs
    leave_type = leave_type.lower().strip()
    if leave_type not in {"annual", "sick"}:
        return "ERROR: leave_type must be annual or sick."

    if noofdays <= 0:
        return "ERROR: days must be greater than zero."

    try:
        start_date = datetime.fromisoformat(start_date).date()
        end_date = datetime.fromisoformat(end_date).date()
    except ValueError:
        return "ERROR: dates must use YYYY-MM-DD format."

    if end_date < start_date:
        return "ERROR: end_date cannot be before start_date."

    with _db() as conn:
        # 2. Check employee exists
        employee = conn.execute(
            "SELECT * FROM employees WHERE employee_id = ?", (empid,)
        ).fetchone()
        if not employee:
            return "NOT_FOUND: employee does not exist."

        # 3. Fetch leave balance based on leave_type
        if leave_type == "annual":
            available_leaves = float(employee["annual_leave_balance"])
        else:
            available_leaves = float(employee["sick_leave_balance"])

        # 4. Check sufficient balance
        if available_leaves < noofdays:
            return "ERROR: insufficient leave balance."

        # 5. Check for any pending leave request
        requests = conn.execute(
            "SELECT * FROM leave_requests WHERE employee_id = ?", (empid,)
        ).fetchall()

        for req in requests:
            if req["status"] == "pending":
                return "ERROR: employee already has a leave request in progress, cannot create another."

        # 6. Check blacklisted dates in the requested range
        calendar_records = calendar_repo.get_all()
        calendar_lookup = {rec["date"]: bool(rec["isblacklisted"]) for rec in calendar_records}

        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")

            if calendar_lookup.get(date_str, False):
                return f"ERROR: {date_str} is blacklisted due to an important company event, leave cannot be requested on this date. Please choose a different date or contact HR."

            current_date += timedelta(days=1)

        # 7. Create the leave request
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur = conn.execute(
            """INSERT INTO leave_requests
            (employee_id, leave_type, start_date, end_date, days, reason, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (empid, leave_type, start_date, end_date, noofdays, reason, created_at)
        )

        # 8. Deduct balance from the specific leave type
        if leave_type == "annual":
            conn.execute(
                "UPDATE employees SET annual_leave_balance = annual_leave_balance - ? WHERE employee_id = ?",
                (noofdays, empid)
            )
        else:
            conn.execute(
                "UPDATE employees SET sick_leave_balance = sick_leave_balance - ? WHERE employee_id = ?",
                (noofdays, empid)
            )

        conn.commit()
        row = conn.execute(
            "SELECT * FROM leave_requests WHERE id = ?", (cur.lastrowid,)
        ).fetchone()

    return _rows_to_json([row])


@mcp.tool()
def withdraw_a_leave_in_progress(empid: str) -> str:
    """
        Withdraws an employee's pending leave request.
        Upon successful withdrawal, the leave days are added back to the
        employee's specific leave balance.
    """
    if not empid:
        return "ERROR: employee_id is required."

    with _db() as conn:

        # 1. Check whether the employee has any pending leave request
        pending_request = conn.execute(
            "SELECT * FROM leave_requests WHERE employee_id = ? AND status = 'pending'",
            (empid,)
        ).fetchone()

        if pending_request is None:
            return "NOT_FOUND: no pending leave request found for this employee."

        # 2. Update the status of the leave to 'cancelled'
        request_id = pending_request["id"]
        conn.execute(
            "UPDATE leave_requests SET status = 'cancelled' WHERE id = ?",
            (request_id,)
        )

        # 3. Restore the leave days to the employee's specific balance
        leave_type = pending_request["leave_type"]
        days = float(pending_request["days"])

        if leave_type == "annual":
            conn.execute(
                "UPDATE employees SET annual_leave_balance = annual_leave_balance + ? WHERE employee_id = ?",
                (days, empid)
            )
        else:  # sick
            conn.execute(
                "UPDATE employees SET sick_leave_balance = sick_leave_balance + ? WHERE employee_id = ?",
                (days, empid)
            )

        conn.commit()

        # 4. Return the updated leave request
        row = conn.execute(
            "SELECT * FROM leave_requests WHERE id = ?", (request_id,)
        ).fetchone()

    return _rows_to_json([row])


@mcp.tool()
def update_days_of_an_accepted_leave(empid: str, newleavedays: float) -> str:
    """
        Update the number of days of a pending leave request.
        Rechecks balance and blacklisted dates, updates end_date based on
        start_date + newleavedays, and adjusts the employee's leave balance.
    """
    if not empid:
        return "ERROR: employee_id is required."

    if newleavedays <= 0:
        return "ERROR: new leave days must be greater than zero."

    if newleavedays > 4:
        return "ERROR: maximum consecutive leaves allowed is 4."

    with _db() as conn:
        # 1. Fetch the pending leave request
        request = conn.execute(
            "SELECT * FROM leave_requests WHERE employee_id = ? AND status = 'pending'",
            (empid,)
        ).fetchone()

        if not request:
            return "NOT_FOUND: no pending leave request found for this employee."

        record_days = float(request["days"])

        # 2. If new days == record days → reject
        if record_days == newleavedays:
            return "ERROR: new leave days are the same as the existing record."

        # 3. Fetch employee
        employee = conn.execute(
            "SELECT * FROM employees WHERE employee_id = ?", (empid,)
        ).fetchone()
        if not employee:
            return "NOT_FOUND: employee does not exist."

        leave_type = request["leave_type"]
        request_id = request["id"]

        # 4. Compute new end_date from start_date + newleavedays
        start_date = datetime.fromisoformat(request["start_date"]).date()
        new_end_date = start_date + timedelta(days=int(newleavedays) - 1)
        new_end_date_str = new_end_date.strftime("%Y-%m-%d")

        # 5. Check blacklisted dates in the new range
        calendar_records = calendar_repo.get_all()
        calendar_lookup = {rec["date"]: bool(rec["isblacklisted"]) for rec in calendar_records}

        current = start_date
        while current <= new_end_date:
            date_str = current.strftime("%Y-%m-%d")
            if calendar_lookup.get(date_str, False):
                return f"ERROR: {date_str} is blacklisted, cannot update leave days."
            current += timedelta(days=1)

        # 6. Handle increase vs decrease
        if newleavedays > record_days:
            # Increasing → check balance
            diff = newleavedays - record_days

            if leave_type == "annual":
                if diff > float(employee["annual_leave_balance"]):
                    return "ERROR: insufficient annual leave balance."
            else:
                if diff > float(employee["sick_leave_balance"]):
                    return "ERROR: insufficient sick leave balance."

            # Update days, end_date, deduct diff
            conn.execute(
                "UPDATE leave_requests SET days = ?, end_date = ? WHERE id = ?",
                (newleavedays, new_end_date_str, request_id)
            )
            if leave_type == "annual":
                conn.execute(
                    "UPDATE employees SET annual_leave_balance = annual_leave_balance - ? WHERE employee_id = ?",
                    (diff, empid)
                )
            else:
                conn.execute(
                    "UPDATE employees SET sick_leave_balance = sick_leave_balance - ? WHERE employee_id = ?",
                    (diff, empid)
                )

        else:
            # Decreasing → refund diff
            diff = record_days - newleavedays

            conn.execute(
                "UPDATE leave_requests SET days = ?, end_date = ? WHERE id = ?",
                (newleavedays, new_end_date_str, request_id)
            )
            if leave_type == "annual":
                conn.execute(
                    "UPDATE employees SET annual_leave_balance = annual_leave_balance + ? WHERE employee_id = ?",
                    (diff, empid)
                )
            else:
                conn.execute(
                    "UPDATE employees SET sick_leave_balance = sick_leave_balance + ? WHERE employee_id = ?",
                    (diff, empid)
                )

        conn.commit()
        row = conn.execute(
            "SELECT * FROM leave_requests WHERE id = ?", (request_id,)
        ).fetchone()

    return _rows_to_json([row])


# ---------------------------------------------------------------------------
# MCP resources — read-only reference data clients can subscribe to
# ---------------------------------------------------------------------------
@mcp.resource("business://policies/priorities")
def priority_policy() -> str:
    """How ticket priorities map to SLA response times."""
    return json.dumps({
        "urgent": "respond < 1h", "high": "respond < 4h",
        "normal": "respond < 24h", "low": "respond < 72h",
    })


if __name__ == "__main__":
    # stdio transport: the agent launches this process and talks over pipes.
    # For network deployment use: mcp.run(transport="sse")
    mcp.run(transport="stdio")
