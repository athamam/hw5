"""Smoke test for the Campus Customs MCP server.

Starts the campus-customs server from .mcp.json (with this Python, so it works on
Windows, macOS and Linux), calls each tool over MCP, checks every returned value
against a direct read of data/campus_customs_new.db, and saves the evidence to
output/mcp_smoke.json. Earlier results are kept under "previous_runs", each with a
snapshot of the database state it was tested against.

Run from the hw5 folder:
    .venv/Scripts/python tests/mcp_smoke_test.py
"""

import asyncio
import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

from fastmcp import Client

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"
OUT_PATH = ROOT / "output" / "mcp_smoke.json"

TESTS = [
    {
        "ticket": 101,
        "vibe_coder_prompt": (
            "Ticket 101: Tauhid Zaman wants one Classic Bulldog Tee in size S. "
            "Use the campus-customs MCP server to check how many CC-TEE-WHITE "
            "in size S we have on hand."
        ),
        "tool": "check_stock",
        "arguments": {"sku": "CC-TEE-WHITE", "size": "S"},
    },
    {
        "ticket": 102,
        "vibe_coder_prompt": (
            "Ticket 102: Elm City Properties sent a rent notice. "
            "Use the campus-customs MCP server to look up lease 1 and tell me "
            "the rent amount, the next due date and how many days are left."
        ),
        "tool": "get_lease",
        "arguments": {"lease_id": 1},
    },
    {
        "ticket": 103,
        "vibe_coder_prompt": (
            "Ticket 103: the Yale AI Club wants 20 CC-HOOD-NAVY hoodies at a bulk "
            "discount. Use the campus-customs MCP server to get the unit cost, "
            "list price and margin for 20 of them."
        ),
        "tool": "get_pricing",
        "arguments": {"sku": "CC-HOOD-NAVY", "qty": 20},
    },
]


def expected_from_db(tool: str, args: dict) -> dict:
    """Read the same facts straight from the database, independent of the server."""
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if tool == "check_stock":
            row = conn.execute(
                "SELECT name, qty, location FROM inventory WHERE sku = ? AND size = ?",
                (args["sku"], args["size"]),
            ).fetchone()
            return {"name": row["name"], "qty": row["qty"], "location": row["location"]}
        if tool == "get_lease":
            row = conn.execute(
                "SELECT landlord, monthly_rent, next_due FROM leases WHERE id = ?",
                (args["lease_id"],),
            ).fetchone()
            today = conn.execute("SELECT date_today FROM desk").fetchone()[0]
            days = (date.fromisoformat(row["next_due"]) - date.fromisoformat(today)).days
            return {
                "landlord": row["landlord"],
                "monthly_rent": row["monthly_rent"],
                "next_due": row["next_due"],
                "date_today": today,
                "days_until_due": days,
            }
        if tool == "get_pricing":
            row = conn.execute(
                "SELECT unit_cost, list_price FROM pricing WHERE sku = ?",
                (args["sku"],),
            ).fetchone()
            return {
                "unit_cost": row["unit_cost"],
                "list_price": row["list_price"],
                "total_cost": round(row["unit_cost"] * args["qty"], 2),
            }
    finally:
        conn.close()
    raise ValueError(f"Unknown tool {tool}")


def db_snapshot() -> dict:
    """The database state the tools were tested against, so outputs can be checked later."""
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        return {
            "date_today": conn.execute("SELECT date_today FROM desk").fetchone()[0],
            "checking_balance": conn.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()[0],
            "ticket_statuses": dict(conn.execute("SELECT id, status FROM tickets ORDER BY id").fetchall()),
            "lease_1_next_due": conn.execute("SELECT next_due FROM leases WHERE id = 1").fetchone()[0],
            "payments_recorded": conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0],
        }
    finally:
        conn.close()


def flatten_for_check(tool: str, output: dict) -> dict:
    """Pull the fields we compare out of the tool output."""
    if tool == "check_stock":
        item = output["items"][0]
        return {"name": item["name"], "qty": item["qty"], "location": item["location"]}
    return output


async def main() -> None:
    config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    server = config["mcpServers"]["campus-customs"]
    server["command"] = sys.executable
    server["args"] = [str(ROOT / a) if a.endswith(".py") else a for a in server.get("args", [])]
    server["cwd"] = str(ROOT)

    results = []
    async with Client(config) as client:
        listed = sorted(t.name for t in await client.list_tools())
        for test in TESTS:
            result = await client.call_tool(test["tool"], test["arguments"])
            output = result.structured_content or json.loads(result.content[0].text)
            expected = expected_from_db(test["tool"], test["arguments"])
            actual = flatten_for_check(test["tool"], output)
            mismatches = {k: {"db": v, "tool": actual.get(k)} for k, v in expected.items() if actual.get(k) != v}
            results.append(
                {
                    "ticket": test["ticket"],
                    "vibe_coder_prompt": test["vibe_coder_prompt"],
                    "tool": test["tool"],
                    "arguments": test["arguments"],
                    "tool_output": output,
                    "db_values_checked": expected,
                    "matches_db": not mismatches,
                    "mismatches": mismatches,
                }
            )

    evidence = {
        "server": "campus-customs",
        "connection": ".mcp.json",
        "database": "data/campus_customs_new.db",
        "tested_at": datetime.now().isoformat(timespec="seconds"),
        "db_snapshot": db_snapshot(),
        "tools_listed_by_server": listed,
        "all_passed": all(r["matches_db"] for r in results),
        "tests": results,
    }
    if OUT_PATH.exists():  # keep earlier evidence instead of overwriting it
        old = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        previous = old.pop("previous_runs", [])
        evidence["previous_runs"] = [*previous, old]
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
