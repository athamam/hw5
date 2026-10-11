"""accounting agent: Watches cash and invoices, checks margins, and prepares payments, purchase orders and price overrides for human approval.

Prompt: backend/prompts/accounting.md (after backend/prompts/shop_rules.md)
Output: AgentReport
MCP tools: see AGENT_TOOLS["accounting"] in backend/mcp_tools.py
"""

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.toolsets import AbstractToolset

from backend.agents.base import make_agent
from backend.models import AgentReport, TeamDeps

NAME = "accounting"
DESCRIPTION = "Watches cash and invoices, checks margins, and prepares payments, purchase orders and price overrides for human approval."
OUTPUT_TYPE = AgentReport


def build(model: Model, tools: AbstractToolset[TeamDeps]) -> Agent[TeamDeps, AgentReport]:
    return make_agent(NAME, OUTPUT_TYPE, model, tools)
