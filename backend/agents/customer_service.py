"""customer_service agent: Drafts messages for customers and requesters. Drafts stay on the board.

Prompt: backend/prompts/customer_service.md (after backend/prompts/shop_rules.md)
Output: AgentReport
MCP tools: see AGENT_TOOLS["customer_service"] in backend/mcp_tools.py
"""

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.toolsets import AbstractToolset

from backend.agents.base import make_agent
from backend.models import AgentReport, TeamDeps

NAME = "customer_service"
DESCRIPTION = "Drafts messages for customers and requesters. Drafts stay on the board."
OUTPUT_TYPE = AgentReport


def build(model: Model, tools: AbstractToolset[TeamDeps]) -> Agent[TeamDeps, AgentReport]:
    return make_agent(NAME, OUTPUT_TYPE, model, tools)
