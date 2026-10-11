"""Connects the agent team to the Campus Customs MCP server.

This is the ONLY way agents touch shop data: there is no second tools layer.
The server is started from the same .mcp.json the vibe coder uses.

Three guardrails are applied on the client side, on top of the server's own rules:
  1. Each agent only sees the MCP tools its role needs (AGENT_TOOLS).
  2. Human-only tools (pay, approve, reject, reset) are never shown to any agent,
     and a call to one is blocked even if a model tries it anyway.
  3. The `agent` argument on write tools is hidden from the model and filled in
     from the run's deps, so an agent cannot sign its work as another agent.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from typing import Any

from fastmcp import Client
from pydantic_ai import RunContext
from pydantic_ai.mcp import CallToolFunc, MCPToolset
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset

from backend.config import MCP_CONFIG_PATH, MCP_SERVER_NAME, ROOT
from backend.models import AgentName, TeamDeps

READ_TOOLS_ALL = {"get_desk", "get_ticket"}

AGENT_TOOLS: dict[AgentName, set[str]] = {
    "boss": READ_TOOLS_ALL | {
        "list_tickets", "list_approvals", "get_cash_balance",
        "add_ticket_note", "update_ticket_status",
    },
    "inventory": READ_TOOLS_ALL | {
        "check_stock", "get_pricing", "list_vendors", "check_vendor_can_ship", "list_invoices",
        "add_ticket_note",
    },
    "accounting": READ_TOOLS_ALL | {
        "get_cash_balance", "list_invoices", "list_approvals", "get_pricing", "check_stock",
        "list_vendors", "check_vendor_can_ship", "get_lease",
        "request_payment", "create_purchase_order", "propose_price_override", "add_ticket_note",
    },
    "facilities": READ_TOOLS_ALL | {
        "get_lease", "get_cash_balance", "list_approvals", "add_ticket_note",
    },
    "customer_service": READ_TOOLS_ALL | {
        "check_stock", "get_pricing", "list_approvals", "draft_customer_message", "add_ticket_note",
    },
}

# Only a person on the dashboard may call these. No agent ever gets them.
HUMAN_ONLY_TOOLS = {"pay", "approve_request", "reject_request", "reset_database"}

# Write tools take an `agent` argument that the backend fills in.
AGENT_STAMPED_TOOLS = {
    "add_ticket_note", "update_ticket_status", "request_payment",
    "create_purchase_order", "propose_price_override", "draft_customer_message",
}

assert not any(tools & HUMAN_ONLY_TOOLS for tools in AGENT_TOOLS.values())


def _server_config() -> dict[str, Any]:
    """Read the campus-customs entry from .mcp.json and make it run on any computer.

    The server is started with the same Python that runs the backend (the project's
    virtual environment), so it works on Windows, macOS and Linux no matter which
    interpreter path .mcp.json lists for the vibe coder.
    """
    config = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
    server = dict(config["mcpServers"][MCP_SERVER_NAME])
    server["command"] = sys.executable
    server["args"] = [str(ROOT / arg) if arg.endswith(".py") else arg for arg in server.get("args", [])]
    server["cwd"] = str(ROOT)
    return {"mcpServers": {MCP_SERVER_NAME: server}}


async def _stamp_agent(
    ctx: RunContext[TeamDeps], call_tool: CallToolFunc, name: str, args: dict[str, Any]
) -> Any:
    if name in HUMAN_ONLY_TOOLS:
        return {"error": f"{name} is human-only. Ask for human approval on the dashboard instead."}
    if name not in AGENT_TOOLS[ctx.deps.agent_name]:
        return {"error": f"{ctx.deps.agent_name} is not allowed to call {name}. Delegate to the right agent."}
    if name in AGENT_STAMPED_TOOLS:
        args = {**args, "agent": ctx.deps.agent_name}
    return await call_tool(name, args)


def _allowed_for_agent(ctx: RunContext[TeamDeps], tool_def: ToolDefinition) -> bool:
    return tool_def.name in AGENT_TOOLS[ctx.deps.agent_name]


async def _hide_agent_arg(ctx: RunContext[TeamDeps], tool_defs: list[ToolDefinition]) -> list[ToolDefinition]:
    prepared = []
    for td in tool_defs:
        if td.name in AGENT_STAMPED_TOOLS:
            schema = json.loads(json.dumps(td.parameters_json_schema))
            schema.get("properties", {}).pop("agent", None)
            if "required" in schema:
                schema["required"] = [r for r in schema["required"] if r != "agent"]
            td = replace(td, parameters_json_schema=schema)
        prepared.append(td)
    return prepared


def build_mcp_toolset() -> MCPToolset:
    """The raw connection to the MCP server (all tools). Used by the backend for human actions."""
    return MCPToolset(Client(_server_config()), process_tool_call=_stamp_agent, max_retries=2)


def agent_view(toolset: MCPToolset) -> AbstractToolset[TeamDeps]:
    """The per-agent view: role-filtered tools with the `agent` argument hidden."""
    return toolset.filtered(_allowed_for_agent).prepared(_hide_agent_arg)
