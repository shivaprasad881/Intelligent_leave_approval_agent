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

import json
import sqlite3
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from src.config import settings

mcp = FastMCP("business-operations")


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
def lookup_employee(employee_id: int = 0, employee_code: str = "",
                    email: str = "", name: str = "") -> str:
    """Find EXACTLY ONE employee by ID, employee code, email, or exact name.
Do not call this in a loop or for bulk/list lookups — not supported."""
    with _db() as conn:
        if employee_id:
            rows = conn.execute(
                "SELECT * FROM employees WHERE id = ?", (employee_id,)
            ).fetchall()
        elif employee_code:
            rows = conn.execute(
                "SELECT * FROM employees WHERE lower(employee_code) = lower(?)",
                (employee_code,),
            ).fetchall()
        elif email:
            rows = conn.execute(
                "SELECT * FROM employees WHERE lower(email) = lower(?)", (email,)
            ).fetchall()
        elif name:
            rows = conn.execute(
                "SELECT * FROM employees WHERE lower(name) LIKE lower(?)",
                (f"%{name}%",),
            ).fetchall()
        else:
            return "ERROR: provide employee_id, employee_code, email, or name."
    return _rows_to_json(rows) if rows else "NOT_FOUND: no matching employee."


@mcp.tool()
def get_employee_count(department: str = "", status: str = "active") -> str:
    """Count employees, optionally filtered by department and employment status."""
    clauses = []
    params: list[str] = []
    if department:
        clauses.append("lower(department) = lower(?)")
        params.append(department)
    if status:
        clauses.append("lower(status) = lower(?)")
        params.append(status)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with _db() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS employee_count FROM employees{where}", params
        ).fetchone()
    return _rows_to_json([row])


@mcp.tool()
def get_leave_balance(employee_id: int) -> str:
    """Return an employee's current annual and sick leave balances."""
    with _db() as conn:
        row = conn.execute(
            """SELECT id, employee_code, name, annual_leave_balance,
                      sick_leave_balance
               FROM employees WHERE id = ?""",
            (employee_id,),
        ).fetchone()
    return _rows_to_json([row]) if row else "NOT_FOUND: employee does not exist."


@mcp.tool()
def list_employee_leave_requests(employee_id: int, limit: int = 10) -> str:
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
def create_leave_request(employee_id: int, leave_type: str, start_date: str,
                         end_date: str, days: float, reason: str = "") -> str:
    """Create a pending annual or sick leave request for an active employee.

    This records the request only. Policy eligibility must be checked using the
    HR policy document and the employee's leave balance before calling it.
    """
    leave_type = leave_type.lower().strip()
    if leave_type not in {"annual", "sick"}:
        return "ERROR: leave_type must be annual or sick."
    if days <= 0:
        return "ERROR: days must be greater than zero."
    try:
        start = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date()
    except ValueError:
        return "ERROR: dates must use YYYY-MM-DD format."
    if end < start:
        return "ERROR: end_date cannot be before start_date."

    with _db() as conn:
        employee = conn.execute(
            "SELECT * FROM employees WHERE id = ? AND status = 'active'",
            (employee_id,),
        ).fetchone()
        if not employee:
            return "NOT_FOUND: active employee does not exist."
        balance_field = (
            "annual_leave_balance" if leave_type == "annual"
            else "sick_leave_balance"
        )
        if float(employee[balance_field]) < days:
            return (
                f"ERROR: insufficient {leave_type} leave balance; "
                f"available={employee[balance_field]}, requested={days}."
            )
        duplicate = conn.execute(
            """SELECT id FROM leave_requests
               WHERE employee_id = ? AND status IN ('pending', 'approved')
                 AND start_date <= ? AND end_date >= ?""",
            (employee_id, end_date, start_date),
        ).fetchone()
        if duplicate:
            return f"ERROR: overlapping leave request exists (request {duplicate['id']})."

        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """INSERT INTO leave_requests
               (employee_id, leave_type, start_date, end_date, days, reason,
                status, approver_note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', '', ?)""",
            (employee_id, leave_type, start_date, end_date, days, reason, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM leave_requests WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _rows_to_json([row])


@mcp.tool()
def update_leave_request_status(request_id: int, status: str,
                                approver_note: str = "") -> str:
    """Approve or reject a pending leave request.

    On approval, the relevant leave balance is reduced atomically.
    Allowed statuses: approved, rejected, cancelled.
    """
    status = status.lower().strip()
    if status not in {"approved", "rejected", "cancelled"}:
        return "ERROR: status must be approved, rejected, or cancelled."

    with _db() as conn:
        request = conn.execute(
            "SELECT * FROM leave_requests WHERE id = ?", (request_id,)
        ).fetchone()
        if not request:
            return "NOT_FOUND: leave request does not exist."
        if request["status"] != "pending":
            return f"ERROR: request is already {request['status']}."

        if status == "approved":
            balance_field = (
                "annual_leave_balance" if request["leave_type"] == "annual"
                else "sick_leave_balance"
            )
            employee = conn.execute(
                f"SELECT {balance_field} AS balance FROM employees WHERE id = ?",
                (request["employee_id"],),
            ).fetchone()
            if not employee or float(employee["balance"]) < float(request["days"]):
                return "ERROR: employee no longer has sufficient leave balance."
            conn.execute(
                f"UPDATE employees SET {balance_field} = {balance_field} - ? WHERE id = ?",
                (request["days"], request["employee_id"]),
            )

        conn.execute(
            "UPDATE leave_requests SET status = ?, approver_note = ? WHERE id = ?",
            (status, approver_note, request_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM leave_requests WHERE id = ?", (request_id,)
        ).fetchone()
    return _rows_to_json([row])


@mcp.tool()
def get_department_summary() -> str:
    """Return active employee counts grouped by department."""
    with _db() as conn:
        rows = conn.execute(
            """SELECT department, COUNT(*) AS employee_count
               FROM employees WHERE status = 'active'
               GROUP BY department ORDER BY department"""
        ).fetchall()
    return _rows_to_json(rows)


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
