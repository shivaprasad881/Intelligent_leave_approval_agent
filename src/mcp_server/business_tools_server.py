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
def lookup_employee(employee_id: str = "", employee_code: str = "",
                    email: str = "", name: str = "") -> str:
    """Find EXACTLY ONE employee by ID, employee code, email, or exact name.
        Do not call this in a loop or for bulk/list lookups — not supported."""
    with _db() as conn:
        if employee_id:
            rows = conn.execute(
                "SELECT * FROM employees WHERE employee_id = ?", (employee_id,)
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
def get_leave_balance(employee_id: str) -> str:
    """Return an employee's current annual and sick leave balances."""
    with _db() as conn:
        row = conn.execute(
            """SELECT employee_id, employee_code, name, annual_leave_balance,
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


# @mcp.tool()
# def create_leave_request(employee_id: str, leave_type: str, start_date: str,end_date: str, days: float, reason: str = "") -> str:
#     """Create a pending annual or sick leave request for an active employee.

#     This records the request only. Policy eligibility must be checked using the
#     HR policy document and the employee's leave balance before calling it.
#     """
#     leave_type = leave_type.lower().strip()
#     if leave_type not in {"annual", "sick"}:
#         return "ERROR: leave_type must be annual or sick."

    
#     if days <= 0:
#         return "ERROR: days must be greater than zero."


    
#     try:
#         start = datetime.fromisoformat(start_date).date()
#         end = datetime.fromisoformat(end_date).date()
#     except ValueError:
#         return "ERROR: dates must use YYYY-MM-DD format."
#     if end < start:
#         return "ERROR: end_date cannot be before start_date."

#     with _db() as conn:
#         employee = conn.execute(
#             "SELECT * FROM employees WHERE employee_id = ? AND status = 'active'",
#             (employee_id,),
#         ).fetchone()
#         if not employee:
#             return "NOT_FOUND: active employee does not exist."
#         balance_field = (
#             "annual_leave_balance" if leave_type == "annual"
#             else "sick_leave_balance"
#         )
#         if float(employee[balance_field]) < days:
#             return (
#                 f"ERROR: insufficient {leave_type} leave balance; "
#                 f"available={employee[balance_field]}, requested={days}."
#             )
#         duplicate = conn.execute(
#             """SELECT id FROM leave_requests
#                WHERE employee_id = ? AND status IN ('pending', 'approved')
#                  AND start_date <= ? AND end_date >= ?""",
#             (employee_id, end_date, start_date),
#         ).fetchone()
#         if duplicate:
#             return f"ERROR: overlapping leave request exists (request {duplicate['id']})."

#         now = datetime.now(timezone.utc).isoformat()
#         cur = conn.execute(
#             """INSERT INTO leave_requests
#                (employee_id, leave_type, start_date, end_date, days, reason,
#                 status, approver_note, created_at)
#                VALUES (?, ?, ?, ?, ?, ?, 'pending', '', ?)""",
#             (employee_id, leave_type, start_date, end_date, days, reason, now),
#         )

#         # we already verified for correct leave types
#         if(leave_type=="annual"):
#             conn.execute(
#                 "UPDATE employees SET annual_leave_balance = annual_leave_balance - ? WHERE employee_id = ?",
#                 (days, employee_id)
#             )

#         else:
#             conn.execute(
#                 "UPDATE employees SET sick_leave_balance = sick_leave_balance - ? WHERE employee_id = ?",
#                 (days, employee_id)
#             )
            

#         conn.commit()
#         row = conn.execute(
#             "SELECT * FROM leave_requests WHERE id = ?", (cur.lastrowid,)
#         ).fetchone()
#     return _rows_to_json([row])


calender = {
    "2026-09-01": False,
    "2026-09-02": False,
    "2026-09-03": False,
    "2026-09-04": False,
    "2026-09-05": False,
    "2026-09-06": False,
    "2026-09-07": False,
    "2026-09-08": False,
    "2026-09-09": False,
    "2026-09-10": False,
    "2026-09-11": False,
    "2026-09-12": False,
    "2026-09-13": False,
    "2026-09-14": False,
    "2026-09-15": False,
    "2026-09-16": False,
    "2026-09-17": False,
    "2026-09-18": False,
    "2026-09-19": False,
    "2026-09-20": False,
    "2026-09-21": False,
    "2026-09-22": False,
    "2026-09-23": False,
    "2026-09-24": False,
    "2026-09-25": False,
    "2026-09-26": False,
    "2026-09-27": False,
    "2026-09-28": False,
    "2026-09-29": False,
    "2026-09-30": False,
}


@mcp.tool()
def create_leave_request(empid: str, start_date: str,end_date: str, noofdays: float, reason: str, leave_type: str) -> str:

    """
        Creates a leave
        request for the employee after checking for overlapping leave requests
        and verifying the employee's eligibility. On successful creation, the
        requested days are deducted from the employee's specific leave balance.

        This records the request only. Policy eligibility must be checked using the
        HR policy document and the employee's leave balance before calling it.
    """

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
        # check do the employee have any leave requests
        requests = conn.execute(
            "SELECT * FROM leave_requests WHERE employee_id = ?", (empid,)
        ).fetchall()

        # if yes then check their status
        for req in requests:
            # if status is pending then reject
            if req["status"] == "pending":
                return "ERROR: employee already has a leave request in progress, cannot create another."

        # emp doesn't have an in-progress leave, check eligibility
        employee = conn.execute(
            "SELECT * FROM employees WHERE employee_id = ?", (empid,)
        ).fetchone()
        if not employee:
            return "NOT_FOUND: employee does not exist."

        # based on leave_type fetch the available leaves
        if leave_type == "annual":
            available_leaves = float(employee["annual_leave_balance"])
        else:
            available_leaves = float(employee["sick_leave_balance"])

        # if available_leaves < requested_leaves then reject
        if available_leaves < noofdays:
            return "ERROR: insufficient leave balance."

        


        # now check whether any of these dates are in the blacklist or not 

        calendar_records = calendar_repo.get_all()
        calendar_lookup = {rec["date"]: bool(rec["isblacklisted"]) for rec in calendar_records}

        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")

            if calendar_lookup.get(date_str, False):
                return f"ERROR: {date_str} is blacklisted due to an important company event, leave cannot be requested on this date. Please choose a different date or contact HR."

            current_date += timedelta(days=1)

    
        # hoo non of the requested dates are in blacklist , grant the leave 



        

        
        
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # create the leave request
        cur = conn.execute(
            """INSERT INTO leave_requests
            (employee_id, leave_type, start_date, end_date, days, reason, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (empid, leave_type, start_date, end_date, noofdays, reason, created_at)
        )

        # upon successful creation, deduct that noof days from the emp's specific leave balance
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
def update_days_of_an_accepted_leave(empid: str, newleavedays: float) -> str:

    """
        Update the number of days of a pending leave after checking the
        employee's eligibility.

        Parameters:
            empid (str): Employee's ID.
            newleavedays (float): The new leave day count to set.
    """

    with _db() as conn:
        # check whether any leave records available for that empid
        request = conn.execute(
            "SELECT * FROM leave_requests WHERE employee_id = ?", (empid,)
        ).fetchone()

        # if not present reject it
        if not request:
            return "NOT_FOUND: no leave record found for this employee."

        # check the status of the leave it should be pending state
        if request["status"] != "pending":
            return f"ERROR: request is already {request['status']}."

        # get the no of leave days from the leave record
        record_days = float(request["days"])

        # compare it with the requested newleavedays, if both are same reject
        if record_days == newleavedays:
            return "ERROR: new leave days are the same as the existing record."

        # find the leave type from the record
        leave_type = request["leave_type"]
        request_id = request["id"]

        # fetch employee
        employee = conn.execute(
            "SELECT * FROM employees WHERE employee_id = ?", (empid,)
        ).fetchone()
        if not employee:
            return "NOT_FOUND: employee does not exist."

        if newleavedays > record_days:
            # requested_days > record_days, difference is diff
            diff = newleavedays - record_days

            if leave_type == "annual":
                # check whether employee has enough annual leaves
                if diff > float(employee["annual_leave_balance"]):
                    return "ERROR: insufficient annual leave balance."
                # update leave days and reduce balance by diff
                conn.execute(
                    "UPDATE leave_requests SET days = ? WHERE id = ?",
                    (newleavedays, request_id)
                )
                conn.execute(
                    "UPDATE employees SET annual_leave_balance = annual_leave_balance - ? WHERE employee_id = ?",
                    (diff, empid)
                )
            else:
                # check whether employee has enough sick leaves
                if diff > float(employee["sick_leave_balance"]):
                    return "ERROR: insufficient sick leave balance."
                conn.execute(
                    "UPDATE leave_requests SET days = ? WHERE id = ?",
                    (newleavedays, request_id)
                )
                conn.execute(
                    "UPDATE employees SET sick_leave_balance = sick_leave_balance - ? WHERE employee_id = ?",
                    (diff, empid)
                )

        else:
            # requested_days < record_days, find the diff
            diff = record_days - newleavedays

            if leave_type == "annual":
                # update leave days and increment balance by diff
                conn.execute(
                    "UPDATE leave_requests SET days = ? WHERE id = ?",
                    (newleavedays, request_id)
                )
                conn.execute(
                    "UPDATE employees SET annual_leave_balance = annual_leave_balance + ? WHERE employee_id = ?",
                    (diff, empid)
                )
            else:
                conn.execute(
                    "UPDATE leave_requests SET days = ? WHERE id = ?",
                    (newleavedays, request_id)
                )
                conn.execute(
                    "UPDATE employees SET sick_leave_balance = sick_leave_balance + ? WHERE employee_id = ?",
                    (diff, empid)
                )

        conn.commit()
        row = conn.execute(
            "SELECT * FROM leave_requests WHERE id = ?", (request_id,)
        ).fetchone()
    return _rows_to_json([row])



@mcp.tool()
def withdraw_a_leave_in_progress(empid: str) -> str:
    """
        Withdraws an employee's in-progress leave request.
        Upon successful withdrawal, the leave days are added back to the
        employee's available leave balance.
    """ 
    with _db() as conn:

        # fetch all leave requests of the user
        requests = conn.execute(
            "SELECT * FROM leave_requests WHERE employee_id = ?", (empid,)
        ).fetchall()

        # if nothing got, reject it
        if not requests:
            return "NOT_FOUND: no leave record found for this employee."

        # check for any of them that is pending
        pending_request = None
        for req in requests:
            if req["status"] == "pending":
                # encountered a pending, stop there itself
                pending_request = req
                break

        # if no one is pending, reject it
        if pending_request is None:
            return "ERROR: no pending leave request found for this employee."

        # use pending_request from here on
        request = pending_request






        # user had a leave in progress, update status to cancelled
        request_id = request["id"]
        conn.execute(
            "UPDATE leave_requests SET status = 'cancelled' WHERE id = ?",
            (request_id,)
        )

        # find the leave type and days from that record
        leave_type = request["leave_type"]
        days = float(request["days"])

        # access the emp record
        employee = conn.execute(
            "SELECT * FROM employees WHERE employee_id = ?", (empid,)
        ).fetchone()
        if not employee:
            return "NOT_FOUND: employee does not exist."

        # increment the emp's that specific leave days by days
        if leave_type == "annual":
            conn.execute(
                "UPDATE employees SET annual_leave_balance = annual_leave_balance + ? WHERE employee_id = ?",
                (days, empid)
            )
        else:
            conn.execute(
                "UPDATE employees SET sick_leave_balance = sick_leave_balance + ? WHERE employee_id = ?",
                (days, empid)
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
