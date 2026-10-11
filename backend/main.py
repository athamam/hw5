"""Campus Customs operations API (FastAPI).

Start from the backend/ folder:
    uvicorn main:app --reload --port 8000

Every shop fact and every change goes through the Campus Customs MCP server
(one server process, started when the API starts). Agents only *prepare*
payments and purchase orders; the approve route is the only thing that moves
cash, and it calls the MCP server's human-only tools.
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# Allow `uvicorn main:app` from inside backend/ while keeping `backend.*` imports.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend import audit  # noqa: E402
from backend.config import MODEL_NAME  # noqa: E402
from backend.models import TicketRunResult  # noqa: E402
from backend.team import Team  # noqa: E402

team: Team | None = None
# One agent run (or reset) at a time, so the board and the database stay consistent.
work_lock = asyncio.Lock()
running_ticket: int | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global team
    team = Team()
    async with team:
        yield
    team = None


app = FastAPI(title="Campus Customs Operations API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def mcp(tool: str, args: dict[str, Any] | None = None) -> Any:
    """Call an MCP tool; turn a tool-level error into an HTTP error."""
    assert team is not None
    result = await team.call_tool(tool, args)
    if isinstance(result, dict) and "error" in result:
        message = result["error"]
        status = 404 if message.startswith("No ") else 400
        raise HTTPException(status_code=status, detail=message)
    return result


class ApproveBody(BaseModel):
    approved_by: str = Field(min_length=1, description="Name of the human approving.")
    note: str = ""


class RejectBody(BaseModel):
    rejected_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, Any]:
    assert team is not None
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "ai_ready": team.ai_ready,  # False = no PORTKEY_API_KEY: board is read-only, runs are disabled
        "ai_error": team.model_error,
        "busy_with_ticket": running_ticket,
    }


@app.get("/tickets")
async def list_tickets() -> dict[str, Any]:
    """Every ticket on the board, with open/resolved."""
    result = await mcp("list_tickets")
    tickets = [
        {
            **t,
            "is_resolved": t["status"] == "resolved",
            "open_or_resolved": "resolved" if t["status"] == "resolved" else "open",
        }
        for t in result["tickets"]
    ]
    return {"tickets": tickets, "running_ticket": running_ticket}


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int) -> dict[str, Any]:
    """One ticket plus notes, approvals, purchase orders and drafts on it."""
    return await mcp("get_ticket", {"ticket_id": ticket_id})


@app.post("/tickets/{ticket_id}/run", response_model=TicketRunResult)
async def run_ticket(ticket_id: int) -> TicketRunResult:
    """Run the agent team (Boss first) on one ticket. Takes a minute or two."""
    global running_ticket
    await mcp("get_ticket", {"ticket_id": ticket_id})  # 404 if it does not exist
    assert team is not None
    if not team.ai_ready:
        raise HTTPException(status_code=503, detail=team.model_error)
    if work_lock.locked():
        raise HTTPException(status_code=409, detail=f"The team is busy with ticket {running_ticket}.")
    async with work_lock:
        running_ticket = ticket_id
        try:
            assert team is not None
            return await team.run_ticket(ticket_id)
        finally:
            running_ticket = None


@app.get("/events")
async def events(
    limit: int = Query(50, ge=1, le=500),
    ticket_id: int | None = None,
    after: int = Query(-1, description="Only events with index greater than this (for polling)."),
) -> dict[str, Any]:
    """Recent agent events from output/audit_trail.json: who said what and which tools they used."""
    trail = audit.read_all()
    out = []
    for index, step in enumerate(trail):
        if index <= after or (ticket_id is not None and step.get("ticket_id") != ticket_id):
            continue
        detail = step.get("detail", {})
        node = step.get("node")
        said: str | None = None
        tools: list[dict[str, Any]] = []
        final_output: dict[str, Any] | None = None
        if node == "tool_calls":
            texts = [p["content"] for p in detail.get("parts", []) if p["type"] == "text"]
            said = "\n".join(texts) or None
            tools = [
                {"tool": p["tool"], "args": p["args"]}
                for p in detail.get("parts", [])
                if p["type"] == "tool_call" and p["tool"] != "final_result"
            ]
            final = [p["args"] for p in detail.get("parts", []) if p.get("tool") == "final_result"]
            if final and isinstance(final[0], dict):
                said = said or final[0].get("decision") or final[0].get("summary")
        elif node == "end":
            output = detail.get("output")
            if isinstance(output, dict):
                said = output.get("decision") or output.get("summary")
                final_output = output
        elif node == "error":
            said = f"{detail.get('error')}: {detail.get('message')}"
        elif node == "model_request":
            results = [p for p in detail.get("parts", []) if p["type"] == "tool_result"]
            if not results:
                continue  # the first request only repeats the user prompt
            tools = [{"tool": p["tool"], "result": p["result"]} for p in results]
        else:
            continue
        out.append(
            {
                "index": index,
                "timestamp": step["timestamp"],
                "run_id": step["run_id"],
                "ticket_id": step["ticket_id"],
                "agent": step["agent"],
                "delegated_by": step.get("delegated_by"),
                "depth": step.get("depth"),
                "kind": {"tool_calls": "agent_turn", "model_request": "tool_results"}.get(node, node),
                "said": said,
                "tools": tools,
                "usage": step.get("usage", {}),
                "output": final_output,
            }
        )
    return {"events": out[-limit:], "last_index": len(trail) - 1, "running_ticket": running_ticket}


@app.get("/approvals")
async def list_approvals(status: str | None = "pending") -> dict[str, Any]:
    """Requests waiting for a human (or decided ones, with ?status=approved / rejected / all)."""
    return await mcp("list_approvals", {"status": None if status == "all" else status})


@app.post("/approvals/{approval_id}/approve")
async def approve(approval_id: int, body: ApproveBody) -> dict[str, Any]:
    """A human clicked Approve. Payments are paid here (cash changes); POs and price overrides are approved.

    Refused (HTTP 400) if cash would go negative, if a PO's vendor still has an
    open invoice, or if the request is not pending.
    """
    approvals = (await mcp("list_approvals"))["approvals"]
    request = next((a for a in approvals if a["id"] == approval_id), None)
    if request is None:
        raise HTTPException(status_code=404, detail=f"No approval request with id {approval_id}.")
    if request["kind"] == "payment":
        result = await mcp("pay", {"approval_id": approval_id, "approved_by": body.approved_by})
    else:
        result = await mcp(
            "approve_request", {"approval_id": approval_id, "approved_by": body.approved_by, "note": body.note}
        )
    cash = await mcp("get_cash_balance")
    return {"result": result, "cash_balance": cash["total_balance"]}


@app.post("/approvals/{approval_id}/reject")
async def reject(approval_id: int, body: RejectBody) -> dict[str, Any]:
    """A human clicked Reject. No money moves."""
    return await mcp(
        "reject_request", {"approval_id": approval_id, "rejected_by": body.rejected_by, "reason": body.reason}
    )


@app.get("/cash")
async def cash() -> dict[str, Any]:
    """Current checking balance from cash_accounts, plus pending payment requests."""
    result = await mcp("get_cash_balance")
    checking = next((a for a in result["accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(status_code=404, detail="No checking account in cash_accounts.")
    return {
        "account": "checking",
        "balance": checking["balance"],
        "as_of": checking["date"],
        "pending_payment_requests": result["pending_payment_requests"],
        "projected_balance": result["projected_balance"],
    }


@app.post("/reset")
async def reset() -> dict[str, Any]:
    """Restore data/campus_customs_new.db from the original campus_customs.db for a fresh run.

    The audit trail is not wiped; it is append-only.
    """
    if work_lock.locked():
        raise HTTPException(status_code=409, detail=f"Cannot reset while the team is working ticket {running_ticket}.")
    async with work_lock:
        return await mcp("reset_database")
