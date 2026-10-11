"""Shared building blocks for every Campus Customs agent.

Each agent = its prompt file (backend/prompts/<name>.md, after the shared
shop rules) + the one shared gpt-6-luna model + its role's view of the MCP
tools + a `delegate` tool that can hand work to any other agent.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.toolsets import AbstractToolset

from backend.config import MAX_DELEGATION_DEPTH, MAX_DELEGATIONS_PER_TICKET, MAX_OUTPUT_TOKENS, PROMPTS_DIR
from backend.models import AGENT_NAMES, AgentName, TeamDeps


def load_prompt(name: AgentName) -> str:
    rules = (PROMPTS_DIR / "shop_rules.md").read_text(encoding="utf-8")
    role = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return f"{rules}\n\n{role}"


async def delegate(ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> dict[str, Any]:
    """Hand a task to another agent on the team and get its report back.

    to_agent: one of boss, inventory, accounting, facilities, customer_service.
    task: what you need, naming the ticket id and the exact facts or records you want back.
    """
    me = ctx.deps
    if to_agent == me.agent_name:
        return {"error": "You cannot delegate to yourself. Do the work with your own tools."}
    if to_agent == me.delegated_by:
        return {"error": f"{to_agent} asked you for this work. Report back to them instead of delegating to them."}
    if me.depth + 1 > MAX_DELEGATION_DEPTH:
        return {"error": f"Delegation limit reached (depth {MAX_DELEGATION_DEPTH}). Finish with what you have."}
    if me.state.delegations >= MAX_DELEGATIONS_PER_TICKET:
        return {"error": f"This ticket already used {MAX_DELEGATIONS_PER_TICKET} delegations. Finish with what you have."}

    me.state.delegations += 1
    try:
        output = await me.team.run_agent(to_agent, task, parent=me, usage=ctx.usage)
    except UsageLimitExceeded:
        raise  # the token/request budget is for the whole ticket: stop everything
    except Exception as exc:  # one teammate failing should not crash the whole ticket
        return {"error": f"{to_agent} could not finish: {type(exc).__name__}: {exc}"}
    return output.model_dump()


async def ticket_context(deps: TeamDeps) -> str:
    """Today's date and the ticket row, read once per ticket run from the MCP server,
    so agents do not each spend tool calls fetching the same facts."""
    state = deps.state
    if state.context is None:
        desk = await deps.team.call_tool("get_desk")
        lines = [f"desk.date_today (today for the shop) = {desk['date_today']}."]
        if state.ticket_id is not None:
            ticket = (await deps.team.call_tool("get_ticket", {"ticket_id": state.ticket_id})).get("ticket")
            if ticket:
                fields = {k: v for k, v in ticket.items() if v is not None}
                lines.append(f"Ticket {state.ticket_id} as filed: {json.dumps(fields)}")
        state.context = "\n".join(lines)
    return state.context


def make_agent(
    name: AgentName,
    output_type: type,
    model: Model,
    tools: AbstractToolset[TeamDeps],
) -> Agent[TeamDeps, Any]:
    agent = Agent(
        model,
        name=name,
        deps_type=TeamDeps,
        output_type=output_type,
        instructions=load_prompt(name),
        toolsets=[tools],
        model_settings=ModelSettings(max_tokens=MAX_OUTPUT_TOKENS),
        retries=2,
    )
    agent.tool(delegate, sequential=True)  # one hand-off at a time, never in parallel

    @agent.instructions
    async def who_am_i(ctx: RunContext[TeamDeps]) -> str:
        others = ", ".join(a for a in AGENT_NAMES if a != ctx.deps.agent_name)
        lines = [
            f"You are the {ctx.deps.agent_name} agent. Teammates you can delegate to: {others}.",
            f"Current ticket id: {ctx.deps.state.ticket_id}.",
        ]
        lines.append(await ticket_context(ctx.deps))
        if ctx.deps.delegated_by:
            lines.append(f"This task was delegated to you by {ctx.deps.delegated_by}. Report back to them.")
        return "\n".join(lines)

    return agent
