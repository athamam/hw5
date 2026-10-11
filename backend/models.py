"""Data types for the Campus Customs agent team."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.team import Team

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")

TicketStatus = Literal["open", "in_progress", "waiting_on_human", "resolved"]


# ---------------------------------------------------------------------------
# Run-time dependencies passed to every agent
# ---------------------------------------------------------------------------

@dataclass
class TicketRunState:
    """Shared by every agent working on one ticket run."""

    run_id: str
    ticket_id: int | None
    delegations: int = 0
    step_counter: int = 0
    context: str | None = None  # today's date + ticket row, fetched once from MCP


@dataclass
class TeamDeps:
    """Per-agent deps. `agent_name` is stamped onto every MCP write call,
    so an agent cannot sign its work as another agent."""

    agent_name: AgentName
    team: Team
    state: TicketRunState
    depth: int = 0
    delegated_by: AgentName | None = None
    chain: list[AgentName] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent outputs
# ---------------------------------------------------------------------------

class Fact(BaseModel):
    """A fact an agent relies on, with the MCP tool it came from."""

    fact: str = Field(description="One fact, with numbers, e.g. 'CC-TEE-WHITE size S qty is 0'.")
    source_tool: str = Field(description="The MCP tool that returned this fact, e.g. 'check_stock'.")


class AgentReport(BaseModel):
    """What a specialist agent hands back to whoever delegated to it."""

    agent: AgentName
    ticket_id: int | None
    summary: str = Field(description="Two or three sentences on what you found and did.")
    facts: list[Fact] = Field(default_factory=list)
    actions_taken: list[str] = Field(
        default_factory=list,
        description="Records you created, with their ids: notes, approval requests, POs, drafts.",
    )
    approval_ids: list[int] = Field(default_factory=list, description="Approval requests you created.")
    draft_ids: list[int] = Field(default_factory=list, description="Customer drafts you created.")
    blockers: list[str] = Field(default_factory=list, description="What stops this ticket from being finished.")
    recommendation: str = Field(description="What you think the Boss should decide.")


class BossDecision(BaseModel):
    """The Boss's final call on a ticket."""

    ticket_id: int | None
    assigned_to: list[AgentName] = Field(description="Agents the Boss delegated to.")
    decision: str = Field(description="The final call, in plain words, with the key numbers.")
    ticket_status: TicketStatus
    human_approvals_needed: list[int] = Field(
        default_factory=list, description="Approval ids a human must decide on the dashboard."
    )
    draft_ids: list[int] = Field(default_factory=list, description="Customer drafts waiting on the board.")
    blockers: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

class AuditStep(BaseModel):
    """One step of one agent's loop, appended to output/audit_trail.json."""

    timestamp: str
    run_id: str
    ticket_id: int | None
    step: int = Field(description="Order of this step within the whole ticket run.")
    agent: AgentName
    depth: int
    delegated_by: AgentName | None
    model: str
    node: str = Field(description="user_prompt | model_request | tool_calls | end | error")
    detail: dict[str, Any]
    usage: dict[str, int] = Field(default_factory=dict, description="Cumulative usage for the ticket run.")


class TicketRunResult(BaseModel):
    """Returned after the Boss finishes one ticket."""

    run_id: str
    ticket_id: int | None
    decision: BossDecision | None
    error: str | None = None
    usage: dict[str, int]
    audit_steps: int
