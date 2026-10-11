"""Campus Customs MCP server.

The single source of shop facts for the Campus Customs agent team.
Every tool works on data/campus_customs_new.db (the working copy).
The original data/campus_customs.db is never written to; reset_database
copies it back over the working copy.

Rules enforced here, not just in prompts:
  - "Today" is desk.date_today, never the computer clock.
  - Vendor lead times come from vendors.lead_days.
  - A vendor with an open (unpaid) invoice will not ship, so purchase orders
    to that vendor cannot be approved until the invoice is paid.
  - Money only moves through pay(), which needs a pending payment request and
    a human approver, and refuses if cash would go negative.
  - Cash only goes out. No tool adds money to cash_accounts.
  - Customer messages are saved as drafts. Nothing is ever sent.
  - Tools return what is in the database, or an error. They never guess.

Agent-facing vs human-only tools: pay, approve_request, reject_request and
reset_database are for the human (dashboard/backend). The backend never gives
them to an agent, and they also refuse approver names that belong to agents.
"""

import json
import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path

from fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "campus_customs_new.db"
ORIGINAL_DB_PATH = DATA_DIR / "campus_customs.db"

AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service"}
TICKET_STATUSES = {"open", "in_progress", "waiting_on_human", "resolved"}

# Tables the agent workflow needs that are not in the original database.
# They are created in the working copy only (and again after every reset).
WORKFLOW_SCHEMA = """
CREATE TABLE IF NOT EXISTS ticket_updates (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    agent TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- payment | purchase_order | price_override
    ticket_id INTEGER,
    ref_type TEXT NOT NULL,          -- invoice | lease | purchase_order | pricing
    ref_id TEXT NOT NULL,
    amount REAL NOT NULL,
    details TEXT,                    -- JSON with the facts behind the request
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL,            -- pending | approved | rejected
    decided_by TEXT,
    decided_at TEXT,
    decision_note TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY,
    vendor_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    total REAL NOT NULL,
    ticket_id INTEGER,
    status TEXT NOT NULL,            -- pending_approval | approved | rejected
    expected_arrival TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (vendor_id) REFERENCES vendors(id)
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    drafted_by TEXT NOT NULL,
    status TEXT NOT NULL,            -- always 'draft': nothing is sent
    created_at TEXT NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);
"""

mcp = FastMCP("Campus Customs")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_schema() -> None:
    with _connect_write() as conn:
        conn.executescript(WORKFLOW_SCHEMA)


@contextmanager
def _connect_readonly() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def _connect_write() -> Iterator[sqlite3.Connection]:
    """One transaction per tool call: commit on success, roll back on error."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _today(conn: sqlite3.Connection) -> str:
    """The shop's 'today' comes from desk.date_today, not the system clock."""
    return conn.execute("SELECT date_today FROM desk").fetchone()["date_today"]


def _now() -> str:
    """Wall-clock timestamp, used only to order records for auditing."""
    return datetime.now().isoformat(timespec="seconds")


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _add_one_month(iso_day: str) -> str:
    d = date.fromisoformat(iso_day)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, monthrange(year, month)[1])).isoformat()


def _open_invoices_for_vendor(conn: sqlite3.Connection, vendor_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id, amount, due_date, status, description FROM invoices "
        "WHERE vendor_id = ? AND status != 'paid'",
        (vendor_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _ticket_exists(conn: sqlite3.Connection, ticket_id: int) -> bool:
    return conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is not None


def _check_human(name: str) -> str | None:
    if not name or not name.strip():
        return "A human approver name is required."
    if name.strip().lower() in AGENT_NAMES:
        return f"'{name}' is an agent. Only a human can approve, reject or pay."
    return None


# ---------------------------------------------------------------------------
# Read tools: desk, tickets
# ---------------------------------------------------------------------------

@mcp.tool
def get_desk() -> dict:
    """Get the shop's desk: today's date (desk.date_today) and any desk notes.

    Always use this date as "today" when deciding what is due or overdue.
    """
    with _connect_readonly() as conn:
        row = conn.execute("SELECT date_today, notes FROM desk").fetchone()
    return dict(row)


@mcp.tool
def list_tickets(status: str | None = None) -> dict:
    """List tickets on the board, optionally only those with a given status.

    Statuses: open, in_progress, waiting_on_human, resolved.
    """
    with _connect_readonly() as conn:
        if status:
            rows = conn.execute("SELECT * FROM tickets WHERE status = ? ORDER BY id", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
    return {"tickets": [dict(r) for r in rows]}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Get one ticket plus everything the team has done on it so far:
    notes, approval requests, purchase orders and customer drafts.
    """
    with _connect_readonly() as conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return {"error": f"No ticket found with id {ticket_id}."}
        updates = conn.execute(
            "SELECT * FROM ticket_updates WHERE ticket_id = ? ORDER BY id", (ticket_id,)
        ).fetchall()
        approvals = conn.execute(
            "SELECT * FROM approvals WHERE ticket_id = ? ORDER BY id", (ticket_id,)
        ).fetchall()
        pos = conn.execute(
            "SELECT * FROM purchase_orders WHERE ticket_id = ? ORDER BY id", (ticket_id,)
        ).fetchall()
        drafts = conn.execute(
            "SELECT * FROM drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,)
        ).fetchall()
    return {
        "ticket": dict(ticket),
        "updates": [dict(r) for r in updates],
        "approvals": [{**dict(r), "details": json.loads(r["details"]) if r["details"] else None} for r in approvals],
        "purchase_orders": [dict(r) for r in pos],
        "drafts": [dict(r) for r in drafts],
    }


# ---------------------------------------------------------------------------
# Read tools: inventory, pricing, vendors
# ---------------------------------------------------------------------------

@mcp.tool
def check_stock(sku: str, size: str | None = None) -> dict:
    """Check how many units of a product are on hand, by SKU and size.

    Reads the inventory table. Pass a size (e.g. "S", "M", "OS") to check one
    size, or leave it out to list every size of that SKU.
    """
    with _connect_readonly() as conn:
        if size:
            rows = conn.execute(
                "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
                (sku, size),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ?",
                (sku,),
            ).fetchall()

    if not rows:
        target = f"{sku} size {size}" if size else sku
        return {"error": f"No inventory record found for {target}."}

    return {
        "sku": sku,
        "items": [
            {**dict(row), "in_stock": row["qty"] > 0} for row in rows
        ],
    }


@mcp.tool
def get_pricing(sku: str, qty: int = 1) -> dict:
    """Get a product's unit cost, list price and margin, optionally for a quantity.

    Reads the pricing table. Use this before agreeing to any discount so the
    price never drops below what the shop paid for the product.
    """
    if qty < 1:
        return {"error": "qty must be at least 1."}

    with _connect_readonly() as conn:
        row = conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
            (sku,),
        ).fetchone()

    if row is None:
        return {"error": f"No pricing found for SKU {sku}."}

    unit_cost = row["unit_cost"]
    list_price = row["list_price"]
    unit_margin = list_price - unit_cost
    return {
        "sku": sku,
        "qty": qty,
        "unit_cost": unit_cost,
        "list_price": list_price,
        "unit_margin": round(unit_margin, 2),
        "margin_pct": round(unit_margin / list_price * 100, 1),
        "total_cost": round(unit_cost * qty, 2),
        "total_at_list_price": round(list_price * qty, 2),
    }


@mcp.tool
def list_vendors(specialty: str | None = None) -> dict:
    """List vendors with their specialty and lead time in days.

    Optionally filter by a word in the specialty (e.g. "apparel", "mugs").
    """
    with _connect_readonly() as conn:
        if specialty:
            rows = conn.execute(
                "SELECT * FROM vendors WHERE specialty LIKE ? ORDER BY id", (f"%{specialty}%",)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM vendors ORDER BY id").fetchall()
    return {"vendors": [dict(r) for r in rows]}


@mcp.tool
def check_vendor_can_ship(vendor_id: int) -> dict:
    """Check whether a vendor will ship new product, and when it would arrive.

    A vendor will not ship while it has any open (unpaid) invoice. If it can
    ship, the earliest arrival is desk.date_today + vendors.lead_days.
    """
    with _connect_readonly() as conn:
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return {"error": f"No vendor found with id {vendor_id}."}
        today = _today(conn)
        open_invoices = _open_invoices_for_vendor(conn, vendor_id)

    for inv in open_invoices:
        inv["days_overdue"] = max(0, _days_between(inv["due_date"], today))
    can_ship = not open_invoices
    arrival = (date.fromisoformat(today) + timedelta(days=vendor["lead_days"])).isoformat()
    return {
        "vendor": dict(vendor),
        "date_today": today,
        "can_ship": can_ship,
        "blocking_invoices": open_invoices,
        "earliest_arrival_if_ordered_today": arrival if can_ship else None,
        "earliest_arrival_once_unblocked": arrival,
    }


# ---------------------------------------------------------------------------
# Read tools: money and space
# ---------------------------------------------------------------------------

@mcp.tool
def list_invoices(status: str | None = None, vendor_id: int | None = None) -> dict:
    """List vendor invoices with vendor name and how many days each is overdue.

    Optional filters: status (e.g. "open", "paid") and vendor_id.
    Overdue is measured against desk.date_today.
    """
    sql = (
        "SELECT i.*, v.name AS vendor_name FROM invoices i "
        "JOIN vendors v ON v.id = i.vendor_id WHERE 1=1"
    )
    params: list = []
    if status:
        sql += " AND i.status = ?"
        params.append(status)
    if vendor_id is not None:
        sql += " AND i.vendor_id = ?"
        params.append(vendor_id)
    with _connect_readonly() as conn:
        today = _today(conn)
        rows = conn.execute(sql + " ORDER BY i.id", params).fetchall()

    invoices = []
    for r in rows:
        inv = dict(r)
        days_late = _days_between(inv["due_date"], today)
        inv["is_overdue"] = inv["status"] != "paid" and days_late > 0
        inv["days_overdue"] = max(0, days_late) if inv["status"] != "paid" else 0
        invoices.append(inv)
    return {"date_today": today, "invoices": invoices}


@mcp.tool
def get_lease(lease_id: int) -> dict:
    """Look up a shop lease: rent amount, landlord and when the next rent is due.

    Reads the leases table and compares next_due with desk.date_today to report
    how many days are left (negative means overdue).
    """
    with _connect_readonly() as conn:
        row = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if row is None:
            return {"error": f"No lease found with id {lease_id}."}
        today = _today(conn)

    days_until_due = _days_between(today, row["next_due"])
    return {
        **dict(row),
        "date_today": today,
        "days_until_due": days_until_due,
        "is_overdue": days_until_due < 0,
    }


@mcp.tool
def get_cash_balance() -> dict:
    """Get cash on hand, and what it would be after every pending payment request.

    Cash only goes out in this shop. Use projected_balance to see whether all
    pending payments can be covered without going negative.
    """
    with _connect_readonly() as conn:
        accounts = [dict(r) for r in conn.execute("SELECT * FROM cash_accounts").fetchall()]
        pending = [
            dict(r)
            for r in conn.execute(
                "SELECT id, ref_type, ref_id, amount, reason FROM approvals "
                "WHERE kind = 'payment' AND status = 'pending' ORDER BY id"
            ).fetchall()
        ]
        today = _today(conn)
    balance = sum(a["balance"] for a in accounts)
    pending_total = sum(p["amount"] for p in pending)
    return {
        "date_today": today,
        "accounts": accounts,
        "total_balance": round(balance, 2),
        "pending_payment_requests": pending,
        "pending_total": round(pending_total, 2),
        "projected_balance": round(balance - pending_total, 2),
    }


@mcp.tool
def list_approvals(status: str | None = None) -> dict:
    """List requests waiting for (or decided by) a human: payments, purchase
    orders and price overrides. Optional status filter: pending, approved, rejected.
    """
    with _connect_readonly() as conn:
        if status:
            rows = conn.execute("SELECT * FROM approvals WHERE status = ? ORDER BY id", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM approvals ORDER BY id").fetchall()
    approvals = []
    for r in rows:
        a = dict(r)
        a["details"] = json.loads(a["details"]) if a["details"] else None
        approvals.append(a)
    return {"approvals": approvals}


# ---------------------------------------------------------------------------
# Write tools for agents (nothing here moves money or contacts anyone)
# ---------------------------------------------------------------------------

@mcp.tool
def add_ticket_note(ticket_id: int, agent: str, note: str) -> dict:
    """Post a note on a ticket so the board shows what an agent found or did."""
    with _connect_write() as conn:
        if not _ticket_exists(conn, ticket_id):
            return {"error": f"No ticket found with id {ticket_id}."}
        cur = conn.execute(
            "INSERT INTO ticket_updates (ticket_id, agent, note, created_at) VALUES (?, ?, ?, ?)",
            (ticket_id, agent, note, _now()),
        )
    return {"ok": True, "update_id": cur.lastrowid, "ticket_id": ticket_id}


@mcp.tool
def update_ticket_status(ticket_id: int, status: str, agent: str, resolution: str) -> dict:
    """Move a ticket to a new status and record why. Boss makes this call.

    Statuses: open, in_progress, waiting_on_human, resolved.
    """
    if status not in TICKET_STATUSES:
        return {"error": f"Status must be one of {sorted(TICKET_STATUSES)}."}
    with _connect_write() as conn:
        row = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"error": f"No ticket found with id {ticket_id}."}
        if status == "resolved":
            pending = conn.execute(
                "SELECT COUNT(*) FROM approvals WHERE ticket_id = ? AND status = 'pending'",
                (ticket_id,),
            ).fetchone()[0]
            if pending:
                return {
                    "error": f"Ticket {ticket_id} still has {pending} request(s) waiting for a human. "
                    "Use status 'waiting_on_human' until they are decided."
                }
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        conn.execute(
            "INSERT INTO ticket_updates (ticket_id, agent, note, created_at) VALUES (?, ?, ?, ?)",
            (ticket_id, agent, f"Status {row['status']} -> {status}: {resolution}", _now()),
        )
    return {"ok": True, "ticket_id": ticket_id, "old_status": row["status"], "new_status": status}


@mcp.tool
def request_payment(kind: str, ref_id: int, reason: str, agent: str, ticket_id: int | None = None) -> dict:
    """Prepare a payment for HUMAN approval. This does not pay anything.

    kind is "invoice" (ref_id = invoices.id) or "rent" (ref_id = leases.id).
    The amount is taken from the database, never from the caller. The request
    lands in the approvals queue; only a human can pay it.
    """
    if kind not in {"invoice", "rent"}:
        return {"error": "kind must be 'invoice' or 'rent'."}
    with _connect_write() as conn:
        today = _today(conn)
        if kind == "invoice":
            inv = conn.execute(
                "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
                "WHERE i.id = ?",
                (ref_id,),
            ).fetchone()
            if inv is None:
                return {"error": f"No invoice found with id {ref_id}."}
            if inv["status"] == "paid":
                return {"error": f"Invoice {ref_id} is already paid."}
            amount = inv["amount"]
            ref_type = "invoice"
            details = {
                "payee": inv["vendor_name"],
                "vendor_id": inv["vendor_id"],
                "invoice_description": inv["description"],
                "due_date": inv["due_date"],
                "days_overdue": max(0, _days_between(inv["due_date"], today)),
            }
        else:
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if lease is None:
                return {"error": f"No lease found with id {ref_id}."}
            amount = lease["monthly_rent"]
            ref_type = "lease"
            details = {
                "payee": lease["landlord"],
                "space_name": lease["space_name"],
                "rent_due_date": lease["next_due"],
                "days_until_due": _days_between(today, lease["next_due"]),
            }

        dup = conn.execute(
            "SELECT id FROM approvals WHERE kind = 'payment' AND ref_type = ? AND ref_id = ? "
            "AND status = 'pending'",
            (ref_type, str(ref_id)),
        ).fetchone()
        if dup:
            return {"error": f"A payment request for this {ref_type} is already pending (approval {dup['id']})."}

        balance = conn.execute("SELECT SUM(balance) FROM cash_accounts").fetchone()[0] or 0
        pending_total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM approvals WHERE kind = 'payment' AND status = 'pending'"
        ).fetchone()[0]
        projected = balance - pending_total - amount
        details["cash_balance_now"] = balance
        details["projected_balance_if_all_pending_paid"] = round(projected, 2)

        cur = conn.execute(
            "INSERT INTO approvals (kind, ticket_id, ref_type, ref_id, amount, details, reason, "
            "requested_by, status, created_at) VALUES ('payment', ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (ticket_id, ref_type, str(ref_id), amount, json.dumps(details), reason, agent, _now()),
        )
    result = {
        "ok": True,
        "approval_id": cur.lastrowid,
        "status": "pending",
        "amount": amount,
        "details": details,
        "message": "Waiting for human approval. No money has moved.",
    }
    if projected < 0:
        result["warning"] = (
            f"Not enough cash to cover every pending payment: projected balance {projected:.2f}. "
            "The pay tool will refuse whichever payment would go negative."
        )
    return result


@mcp.tool
def create_purchase_order(
    vendor_id: int, sku: str, size: str, qty: int, reason: str, agent: str, ticket_id: int | None = None
) -> dict:
    """Draft a restock purchase order for HUMAN approval. Nothing is sent to the vendor.

    Unit cost comes from the pricing table. If the vendor has an open invoice,
    the PO is still drafted but cannot be approved until that invoice is paid,
    because the vendor will not ship.
    """
    if qty < 1:
        return {"error": "qty must be at least 1."}
    with _connect_write() as conn:
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return {"error": f"No vendor found with id {vendor_id}."}
        item = conn.execute("SELECT name FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        if item is None:
            return {"error": f"No inventory record for {sku} size {size}."}
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            return {"error": f"No pricing found for SKU {sku}."}
        dup = conn.execute(
            "SELECT id FROM purchase_orders WHERE vendor_id = ? AND sku = ? AND size = ? "
            "AND status = 'pending_approval'",
            (vendor_id, sku, size),
        ).fetchone()
        if dup:
            return {"error": f"A purchase order for {sku} size {size} from this vendor is already pending "
                    f"(PO {dup['id']}). Do not create a duplicate."}
        today = _today(conn)
        blocking = _open_invoices_for_vendor(conn, vendor_id)
        unit_cost = price["unit_cost"]
        total = round(unit_cost * qty, 2)
        arrival = (date.fromisoformat(today) + timedelta(days=vendor["lead_days"])).isoformat()

        po = conn.execute(
            "INSERT INTO purchase_orders (vendor_id, sku, size, qty, unit_cost, total, ticket_id, status, "
            "created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_approval', ?, ?)",
            (vendor_id, sku, size, qty, unit_cost, total, ticket_id, agent, _now()),
        )
        details = {
            "vendor": vendor["name"],
            "item": f"{item['name']} ({sku}) size {size}",
            "qty": qty,
            "unit_cost": unit_cost,
            "lead_days": vendor["lead_days"],
            "earliest_arrival_if_approved_today": arrival,
            "blocked_by_open_invoices": [b["id"] for b in blocking],
        }
        appr = conn.execute(
            "INSERT INTO approvals (kind, ticket_id, ref_type, ref_id, amount, details, reason, "
            "requested_by, status, created_at) VALUES ('purchase_order', ?, 'purchase_order', ?, ?, ?, ?, ?, "
            "'pending', ?)",
            (ticket_id, str(po.lastrowid), total, json.dumps(details), reason, agent, _now()),
        )
    result = {
        "ok": True,
        "purchase_order_id": po.lastrowid,
        "approval_id": appr.lastrowid,
        "status": "pending_approval",
        "total": total,
        "details": details,
        "message": "Draft PO waiting for human approval. Nothing was sent to the vendor.",
    }
    if blocking:
        result["warning"] = (
            f"{vendor['name']} has open invoice(s) {[b['id'] for b in blocking]}, so it will not ship. "
            "This PO cannot be approved until they are paid."
        )
    return result


@mcp.tool
def propose_price_override(
    ticket_id: int, sku: str, qty: int, unit_price: float, reason: str, agent: str
) -> dict:
    """Propose a discounted unit price for HUMAN approval.

    Refuses any price below unit cost (the shop would lose money). Shows the
    discount versus list price and the margin left.
    """
    if qty < 1:
        return {"error": "qty must be at least 1."}
    with _connect_write() as conn:
        if not _ticket_exists(conn, ticket_id):
            return {"error": f"No ticket found with id {ticket_id}."}
        price = conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            return {"error": f"No pricing found for SKU {sku}."}
        if unit_price < price["unit_cost"]:
            return {
                "error": f"Refused: {unit_price:.2f} is below unit cost {price['unit_cost']:.2f}. "
                "The shop would lose money on every unit."
            }
        if unit_price > price["list_price"]:
            return {"error": f"{unit_price:.2f} is above list price {price['list_price']:.2f}; that is not a discount."}
        details = {
            "sku": sku,
            "qty": qty,
            "list_price": price["list_price"],
            "unit_cost": price["unit_cost"],
            "proposed_unit_price": unit_price,
            "discount_pct": round((1 - unit_price / price["list_price"]) * 100, 1),
            "margin_per_unit": round(unit_price - price["unit_cost"], 2),
            "margin_pct": round((unit_price - price["unit_cost"]) / unit_price * 100, 1),
            "order_total": round(unit_price * qty, 2),
            "order_total_at_list": round(price["list_price"] * qty, 2),
        }
        cur = conn.execute(
            "INSERT INTO approvals (kind, ticket_id, ref_type, ref_id, amount, details, reason, "
            "requested_by, status, created_at) VALUES ('price_override', ?, 'pricing', ?, ?, ?, ?, ?, "
            "'pending', ?)",
            (ticket_id, sku, details["order_total"], json.dumps(details), reason, agent, _now()),
        )
    return {
        "ok": True,
        "approval_id": cur.lastrowid,
        "status": "pending",
        "details": details,
        "message": "Price override waiting for human approval.",
    }


@mcp.tool
def draft_customer_message(ticket_id: int, recipient: str, subject: str, body: str, agent: str) -> dict:
    """Save a message to a customer or requester as a DRAFT on the board.

    Nothing is emailed or sent. A human reviews drafts on the dashboard.
    """
    with _connect_write() as conn:
        if not _ticket_exists(conn, ticket_id):
            return {"error": f"No ticket found with id {ticket_id}."}
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, recipient, subject, body, drafted_by, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'draft', ?)",
            (ticket_id, recipient, subject, body, agent, _now()),
        )
    return {"ok": True, "draft_id": cur.lastrowid, "status": "draft", "message": "Saved as a draft. Not sent."}


# ---------------------------------------------------------------------------
# Human-only tools (never given to agents)
# ---------------------------------------------------------------------------

@mcp.tool
def pay(approval_id: int, approved_by: str) -> dict:
    """HUMAN ONLY. Pay a pending payment request after a human approves it.

    Refuses if the request is not a pending payment, if the approver is an
    agent, or if cash on hand is less than the amount (no negative balances).
    On success: deducts cash, records the payment, and marks the invoice paid
    or moves the lease's next rent date forward one month.
    """
    if err := _check_human(approved_by):
        return {"error": err}
    with _connect_write() as conn:
        appr = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if appr is None:
            return {"error": f"No approval request with id {approval_id}."}
        if appr["kind"] != "payment":
            return {"error": f"Approval {approval_id} is a {appr['kind']}, not a payment. Use approve_request."}
        if appr["status"] != "pending":
            return {"error": f"Approval {approval_id} is already {appr['status']}."}

        account = conn.execute("SELECT * FROM cash_accounts ORDER BY balance DESC LIMIT 1").fetchone()
        amount = appr["amount"]
        if account is None or account["balance"] < amount:
            have = account["balance"] if account else 0
            return {
                "error": f"Refused: not enough cash. Need {amount:.2f}, have {have:.2f}. "
                "No money moved and the request is still pending."
            }

        today = _today(conn)
        ref_id = int(appr["ref_id"])
        if appr["ref_type"] == "invoice":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if inv is None or inv["status"] == "paid":
                return {"error": f"Invoice {ref_id} is missing or already paid. No money moved."}
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
            kind = "invoice"
            table_update = f"invoices.id={ref_id} status -> paid"
        else:
            lease = conn.execute("SELECT next_due, notes FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if lease is None:
                return {"error": f"Lease {ref_id} is missing. No money moved."}
            new_due = _add_one_month(lease["next_due"])
            note = f"Rent due {lease['next_due']} paid {today} (approval {approval_id})."
            notes = f"{lease['notes']} {note}" if lease["notes"] else note
            conn.execute("UPDATE leases SET next_due = ?, notes = ? WHERE id = ?", (new_due, notes, ref_id))
            kind = "rent"
            table_update = f"leases.id={ref_id} next_due {lease['next_due']} -> {new_due}"

        new_balance = round(account["balance"] - amount, 2)
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, today, account["name"]),
        )
        pay_row = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, ref_id, amount, account["name"], today, approved_by.strip()),
        )
        conn.execute(
            "UPDATE approvals SET status = 'approved', decided_by = ?, decided_at = ?, decision_note = ? "
            "WHERE id = ?",
            (approved_by.strip(), _now(), f"Paid as payment {pay_row.lastrowid}", approval_id),
        )
    return {
        "ok": True,
        "payment_id": pay_row.lastrowid,
        "amount": amount,
        "account": account["name"],
        "balance_before": account["balance"],
        "balance_after": new_balance,
        "paid_at": today,
        "approved_by": approved_by.strip(),
        "updated": table_update,
    }


@mcp.tool
def approve_request(approval_id: int, approved_by: str, note: str = "") -> dict:
    """HUMAN ONLY. Approve a pending purchase order or price override.

    Payments must go through pay(). A purchase order is refused while its
    vendor still has an open invoice, because the vendor will not ship.
    Approving a PO does not send it to a real vendor.
    """
    if err := _check_human(approved_by):
        return {"error": err}
    with _connect_write() as conn:
        appr = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if appr is None:
            return {"error": f"No approval request with id {approval_id}."}
        if appr["kind"] == "payment":
            return {"error": "This is a payment. Use the pay tool so cash and payments are updated."}
        if appr["status"] != "pending":
            return {"error": f"Approval {approval_id} is already {appr['status']}."}

        result: dict = {"ok": True, "approval_id": approval_id, "kind": appr["kind"]}
        if appr["kind"] == "purchase_order":
            po = conn.execute("SELECT * FROM purchase_orders WHERE id = ?", (int(appr["ref_id"]),)).fetchone()
            blocking = _open_invoices_for_vendor(conn, po["vendor_id"])
            if blocking:
                return {
                    "error": f"Refused: vendor still has open invoice(s) {[b['id'] for b in blocking]} "
                    "and will not ship. Pay them first."
                }
            lead = conn.execute("SELECT lead_days FROM vendors WHERE id = ?", (po["vendor_id"],)).fetchone()[0]
            arrival = (date.fromisoformat(_today(conn)) + timedelta(days=lead)).isoformat()
            conn.execute(
                "UPDATE purchase_orders SET status = 'approved', expected_arrival = ? WHERE id = ?",
                (arrival, po["id"]),
            )
            result.update(purchase_order_id=po["id"], expected_arrival=arrival,
                          message="PO approved. It stays on the board; no real vendor was contacted.")
        conn.execute(
            "UPDATE approvals SET status = 'approved', decided_by = ?, decided_at = ?, decision_note = ? "
            "WHERE id = ?",
            (approved_by.strip(), _now(), note or None, approval_id),
        )
    return result


@mcp.tool
def reject_request(approval_id: int, rejected_by: str, reason: str) -> dict:
    """HUMAN ONLY. Reject a pending payment, purchase order or price override."""
    if err := _check_human(rejected_by):
        return {"error": err}
    with _connect_write() as conn:
        appr = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if appr is None:
            return {"error": f"No approval request with id {approval_id}."}
        if appr["status"] != "pending":
            return {"error": f"Approval {approval_id} is already {appr['status']}."}
        conn.execute(
            "UPDATE approvals SET status = 'rejected', decided_by = ?, decided_at = ?, decision_note = ? "
            "WHERE id = ?",
            (rejected_by.strip(), _now(), reason, approval_id),
        )
        if appr["kind"] == "purchase_order":
            conn.execute("UPDATE purchase_orders SET status = 'rejected' WHERE id = ?", (int(appr["ref_id"]),))
    return {"ok": True, "approval_id": approval_id, "status": "rejected"}


@mcp.tool
def reset_database() -> dict:
    """HUMAN ONLY. Restore the working copy from the original campus_customs.db.

    Run this before every full ticket run. The original file is only read.
    """
    shutil.copyfile(ORIGINAL_DB_PATH, DB_PATH)
    _ensure_schema()
    with _connect_readonly() as conn:
        open_tickets = conn.execute("SELECT COUNT(*) FROM tickets WHERE status = 'open'").fetchone()[0]
        balance = conn.execute("SELECT SUM(balance) FROM cash_accounts").fetchone()[0]
    return {"ok": True, "restored_from": ORIGINAL_DB_PATH.name, "open_tickets": open_tickets, "cash_balance": balance}


_ensure_schema()

if __name__ == "__main__":
    mcp.run(show_banner=False)
