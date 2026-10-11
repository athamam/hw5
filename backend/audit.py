"""Append-only audit trail for the agent team: output/audit_trail.json.

Every step of every agent loop is appended as one JSON object in a list.
The file is never wiped. Earlier runs stay in it, so a reviewer can trace
who did what, with which tool, on which ticket, and at what token cost.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.usage import RunUsage

from backend.config import AUDIT_PATH, AUDIT_TEXT_LIMIT, MODEL_NAME
from backend.models import AuditStep, TeamDeps

_lock = threading.Lock()


def _trim(value: Any) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    if len(text) <= AUDIT_TEXT_LIMIT:
        return value
    return text[:AUDIT_TEXT_LIMIT] + f"... [trimmed {len(text) - AUDIT_TEXT_LIMIT} chars]"


def usage_dict(usage: RunUsage) -> dict[str, int]:
    return {
        "requests": usage.requests,
        "tool_calls": usage.tool_calls,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.input_tokens + usage.output_tokens,
    }


def _request_detail(request: ModelRequest) -> dict[str, Any]:
    """What went INTO the model: the task, or the results of the last tool calls."""
    parts = []
    for part in request.parts:
        if isinstance(part, UserPromptPart):
            parts.append({"type": "user_prompt", "content": _trim(part.content)})
        elif isinstance(part, ToolReturnPart):
            parts.append({"type": "tool_result", "tool": part.tool_name, "result": _trim(part.content)})
        elif isinstance(part, RetryPromptPart):
            parts.append({"type": "retry", "tool": part.tool_name, "content": _trim(part.content)})
    return {"parts": parts}


def _response_detail(response: ModelResponse) -> dict[str, Any]:
    """What came OUT of the model: its text and the tools it decided to call."""
    parts = []
    for part in response.parts:
        if isinstance(part, ToolCallPart):
            parts.append({"type": "tool_call", "tool": part.tool_name, "args": _trim(part.args_as_dict())})
        elif isinstance(part, TextPart):
            parts.append({"type": "text", "content": _trim(part.content)})
        elif isinstance(part, ThinkingPart):
            parts.append({"type": "thinking", "chars": len(part.content or "")})
    return {
        "model_name": response.model_name,
        "parts": parts,
        "response_usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }


def describe_node(node: Any) -> tuple[str, dict[str, Any]]:
    """Turn one agent-loop node into (node type, audit detail)."""
    if Agent.is_user_prompt_node(node):
        return "user_prompt", {"prompt": _trim(node.user_prompt)}
    if Agent.is_model_request_node(node):
        return "model_request", _request_detail(node.request)
    if Agent.is_call_tools_node(node):
        return "tool_calls", _response_detail(node.model_response)
    if Agent.is_end_node(node):
        output = node.data.output
        # Final outputs are kept whole (already capped by MAX_OUTPUT_TOKENS) so the board can summarise them.
        return "end", {"output": output.model_dump() if hasattr(output, "model_dump") else _trim(output)}
    return type(node).__name__, {}


def record(deps: TeamDeps, node: str, detail: dict[str, Any], usage: RunUsage | None) -> None:
    """Append one step for the agent in `deps` to output/audit_trail.json."""
    deps.state.step_counter += 1
    step = AuditStep(
        timestamp=datetime.now().isoformat(timespec="milliseconds"),
        run_id=deps.state.run_id,
        ticket_id=deps.state.ticket_id,
        step=deps.state.step_counter,
        agent=deps.agent_name,
        depth=deps.depth,
        delegated_by=deps.delegated_by,
        model=MODEL_NAME,
        node=node,
        detail=detail,
        usage=usage_dict(usage) if usage else {},
    )
    append([step.model_dump()])


def append(entries: list[dict[str, Any]]) -> None:
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing: list[dict[str, Any]] = []
        if AUDIT_PATH.exists():
            text = AUDIT_PATH.read_text(encoding="utf-8").strip()
            if text:
                existing = json.loads(text)
        existing.extend(entries)
        tmp = AUDIT_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")
        tmp.replace(AUDIT_PATH)


def read_all() -> list[dict[str, Any]]:
    if not AUDIT_PATH.exists():
        return []
    text = AUDIT_PATH.read_text(encoding="utf-8").strip()
    return json.loads(text) if text else []
