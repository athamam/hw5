"""boss agent: Reads each ticket, decides who works on it and makes the final call.

Prompt: backend/prompts/boss.md (after backend/prompts/shop_rules.md)
Output: BossDecision
MCP tools: see AGENT_TOOLS["boss"] in backend/mcp_tools.py
"""

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.toolsets import AbstractToolset

from backend.agents.base import make_agent
from backend.models import BossDecision, TeamDeps

NAME = "boss"
DESCRIPTION = "Reads each ticket, decides who works on it and makes the final call."
OUTPUT_TYPE = BossDecision


def build(model: Model, tools: AbstractToolset[TeamDeps]) -> Agent[TeamDeps, BossDecision]:
    return make_agent(NAME, OUTPUT_TYPE, model, tools)
