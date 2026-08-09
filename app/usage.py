"""Process-local counters for what this instance actually dispatched.

Two numbers are worth showing in an agentic demo: how often the planner
consulted the LLM, and how often a call crossed the MCP boundary. Both are
counted at the single dispatch site for each -- `planner.respond`'s completion
call and `mcp_client`'s `_invoke` wrappers -- so a counter cannot drift from
the thing it claims to count.

Three deliberate properties:

* **Per-process and in-memory.** A free-tier instance sleeps when idle and wakes
  as a new process with the counters at zero. `snapshot()` therefore reports
  when this process started, so a reader sees the window the counts cover
  instead of mistaking them for lifetime totals.
* **Diagnostic calls counted separately.** `/health` reaches the MCP child on
  every probe. Folding those into the agent total would inflate the demo figure
  with health polling, so they are kept in their own bucket.
* **Non-fatal.** Counting must never be able to fail a request, so callers wrap
  nothing in try/except -- the operations here cannot raise on valid input.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

_lock = threading.Lock()

_process_started_at = datetime.now(timezone.utc)
_process_started_monotonic = time.monotonic()

_chat_requests = 0
_llm_calls = 0
_llm_failures = 0
_mcp_discoveries = 0
_mcp_agent_calls: dict[str, int] = {}
_mcp_diagnostic_calls: dict[str, int] = {}
_planners: dict[str, int] = {}


def record_chat_request() -> None:
    """Count one accepted `POST /chat` (after rate limiting, before planning)."""
    global _chat_requests
    with _lock:
        _chat_requests += 1


def record_planner(name: str) -> None:
    """Count which planner produced a response: llm, deterministic, or a gate."""
    with _lock:
        _planners[name] = _planners.get(name, 0) + 1


def record_llm_call() -> None:
    """Count one chat-completion request sent to the provider.

    The planner loop can send several per user question -- one per tool-use
    round trip -- so this is deliberately not the same as `chat_requests`.
    """
    global _llm_calls
    with _lock:
        _llm_calls += 1


def record_llm_failure() -> None:
    """Count one planner run that fell back after the provider failed."""
    global _llm_failures
    with _lock:
        _llm_failures += 1


def record_mcp_discovery() -> None:
    """Count one `list_tools` schema discovery over the MCP session."""
    global _mcp_discoveries
    with _lock:
        _mcp_discoveries += 1


def record_mcp_call(name: str, *, diagnostic: bool = False) -> None:
    """Count one MCP `call_tool` dispatch, keeping health probes out of the total."""
    bucket = _mcp_diagnostic_calls if diagnostic else _mcp_agent_calls
    with _lock:
        bucket[name] = bucket.get(name, 0) + 1


def snapshot() -> dict[str, Any]:
    """Return the counters plus the window they cover. Safe to expose publicly."""
    with _lock:
        agent_calls = dict(sorted(_mcp_agent_calls.items(), key=lambda item: -item[1]))
        diagnostic_calls = dict(sorted(_mcp_diagnostic_calls.items(), key=lambda item: -item[1]))
        return {
            "process_started_at": _process_started_at.isoformat(timespec="seconds"),
            "uptime_seconds": round(time.monotonic() - _process_started_monotonic, 1),
            "counters_are_per_instance": True,
            "chat_requests": _chat_requests,
            "planners": dict(sorted(_planners.items(), key=lambda item: -item[1])),
            "llm": {
                "provider_calls": _llm_calls,
                "provider_failures": _llm_failures,
            },
            "mcp": {
                "tool_calls": sum(agent_calls.values()),
                "by_tool": agent_calls,
                "schema_discoveries": _mcp_discoveries,
                "diagnostic_tool_calls": sum(diagnostic_calls.values()),
                "diagnostic_by_tool": diagnostic_calls,
            },
        }


def reset() -> None:
    """Clear every counter. Used by tests; there is no HTTP route that calls it."""
    global _chat_requests, _llm_calls, _llm_failures, _mcp_discoveries
    with _lock:
        _chat_requests = _llm_calls = _llm_failures = _mcp_discoveries = 0
        _mcp_agent_calls.clear()
        _mcp_diagnostic_calls.clear()
        _planners.clear()
