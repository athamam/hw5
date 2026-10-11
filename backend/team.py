"""The Campus Customs agent team and its agent loop.

    python -m backend.team --ticket 101      # Boss works one ticket
    python -m backend.team --all --reset     # reset the database, then work every open ticket

Every agent uses gpt-6-luna through Portkey. Shop facts come only from the
Campus Customs MCP server. Each step of each agent loop is appended to
output/audit_trail.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from typing import Any

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from openai import AsyncOpenAI  # noqa: E402
from pydantic_ai import Agent  # noqa: E402
from pydantic_ai.exceptions import UsageLimitExceeded  # noqa: E402
from pydantic_ai.mcp import MCPToolset  # noqa: E402
from pydantic_ai.models.openai import OpenAIResponsesModel  # noqa: E402
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402
from pydantic_ai.usage import RunUsage, UsageLimits  # noqa: E402

from backend import audit  # noqa: E402
from backend.agents import AGENT_MODULES  # noqa: E402
from backend.config import (  # noqa: E402
    MAX_MODEL_REQUESTS,
    MAX_TOOL_CALLS,
    MAX_TOTAL_TOKENS,
    MODEL_NAME,
    PORTKEY_BASE_URL,
)
from backend.mcp_tools import agent_view, build_mcp_toolset  # noqa: E402
from backend.models import AgentName, BossDecision, TeamDeps, TicketRunResult, TicketRunState  # noqa: E402

USAGE_LIMITS = UsageLimits(
    request_limit=MAX_MODEL_REQUESTS,
    total_tokens_limit=MAX_TOTAL_TOKENS,
    tool_calls_limit=MAX_TOOL_CALLS,
)


def build_model() -> OpenAIResponsesModel:
    """The one model every agent shares: gpt-6-luna via the Portkey gateway."""
    api_key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set (add it to the course-root .env).")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": api_key, "x-portkey-provider": "openai"},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


class Team:
    """Five agents sharing one model and one MCP connection. Any agent can delegate to any other."""

    def __init__(self) -> None:
        self.model = build_model()
        self.mcp: MCPToolset = build_mcp_toolset()
        tools = agent_view(self.mcp)
        self.agents: dict[AgentName, Agent[TeamDeps, Any]] = {
            name: module.build(self.model, tools) for name, module in AGENT_MODULES.items()
        }

    async def __aenter__(self) -> Team:
        await self.mcp.__aenter__()  # one MCP server process for the whole session
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.mcp.__aexit__(*exc)

    # --- the agent loop -------------------------------------------------------

    async def run_agent(
        self,
        name: AgentName,
        task: str,
        *,
        parent: TeamDeps | None = None,
        state: TicketRunState | None = None,
        usage: RunUsage | None = None,
    ) -> Any:
        """Run one agent's loop step by step, auditing every step.

        Delegated runs share the parent's usage object, so the token and request
        limits apply to the whole ticket, not to each agent separately.
        """
        if parent is not None:
            deps = TeamDeps(
                agent_name=name,
                team=self,
                state=parent.state,
                depth=parent.depth + 1,
                delegated_by=parent.agent_name,
                chain=[*parent.chain, parent.agent_name],
            )
        else:
            assert state is not None
            deps = TeamDeps(agent_name=name, team=self, state=state)

        agent = self.agents[name]
        try:
            async with agent.iter(task, deps=deps, usage=usage, usage_limits=USAGE_LIMITS) as run:
                async for node in run:
                    node_type, detail = audit.describe_node(node)
                    audit.record(deps, node_type, detail, run.usage)
                return run.result.output
        except Exception as exc:  # recorded, then passed up to the Boss / caller
            audit.record(deps, "error", {"error": type(exc).__name__, "message": str(exc)}, usage)
            raise

    # --- entry points ---------------------------------------------------------

    async def run_ticket(self, ticket_id: int) -> TicketRunResult:
        """The Boss works one ticket from start to finish."""
        state = TicketRunState(run_id=uuid.uuid4().hex[:12], ticket_id=ticket_id)
        usage = RunUsage()
        task = (
            f"Work ticket {ticket_id}. Read it, delegate to the right teammates, "
            "make the final call, set the ticket status, and return your decision."
        )
        decision: BossDecision | None = None
        error: str | None = None
        try:
            decision = await self.run_agent("boss", task, state=state, usage=usage)
        except UsageLimitExceeded as exc:
            error = f"Stopped by token/request limit: {exc}"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        return TicketRunResult(
            run_id=state.run_id,
            ticket_id=ticket_id,
            decision=decision,
            error=error,
            usage=audit.usage_dict(usage),
            audit_steps=state.step_counter,
        )

    async def call_tool(self, name: str, args: dict[str, Any] | None = None) -> Any:
        """Direct MCP call for human actions (pay, approve, reject, reset) and board reads."""
        return await self.mcp.direct_call_tool(name, args or {})

    async def reset_database(self) -> Any:
        return await self.call_tool("reset_database")

    async def open_ticket_ids(self) -> list[int]:
        result = await self.call_tool("list_tickets", {"status": "open"})
        return [t["id"] for t in result["tickets"]]


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticket", type=int, help="Ticket id for the Boss to work.")
    group.add_argument("--all", action="store_true", help="Work every open ticket.")
    parser.add_argument("--reset", action="store_true", help="Reset the database to the original first.")
    args = parser.parse_args()

    async with Team() as team:
        if args.reset:
            print("Reset:", json.dumps(await team.reset_database()))
        ids = [args.ticket] if args.ticket else await team.open_ticket_ids()
        for ticket_id in ids:
            result = await team.run_ticket(ticket_id)
            print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
