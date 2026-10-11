"""Shared settings for the Campus Customs agent team.

The model is set in exactly one place: every agent uses MODEL_NAME through
the Portkey gateway. PORTKEY_API_KEY is read from the course-root .env and is
never written to any file in this repo.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent                     # hw5/
PROMPTS_DIR = BACKEND_DIR / "prompts"
OUTPUT_DIR = ROOT / "output"
AUDIT_PATH = OUTPUT_DIR / "audit_trail.json"
MCP_CONFIG_PATH = ROOT / ".mcp.json"
MCP_SERVER_NAME = "campus-customs"

# hw5/.env first (if it exists), then the course root where PORTKEY_API_KEY lives.
load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent.parent / ".env")

# --- Model: the ONLY model used anywhere in hw5 ---
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")

# --- Token and loop limits (per ticket run, shared by every agent in it) ---
MAX_MODEL_REQUESTS = 40          # model calls across all agents on one ticket
MAX_TOTAL_TOKENS = 200_000       # input + output tokens across all agents on one ticket
MAX_TOOL_CALLS = 60              # MCP + delegate tool calls across all agents on one ticket
MAX_OUTPUT_TOKENS = 4_000        # cap on any single model response
MAX_DELEGATION_DEPTH = 3         # boss -> agent -> agent -> agent, no deeper
MAX_DELEGATIONS_PER_TICKET = 10  # total hand-offs between agents on one ticket
AUDIT_TEXT_LIMIT = 2_000         # long text in the audit trail is trimmed to this many characters
