"""Configuration. Secrets come from the environment and are never committed."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_DIR = ROOT / "data" / "policies"
DATA_DIR = ROOT / "data"
# Synthetic employee records live in mock_data/ at the repository root, the
# location the project brief asks for.
MOCK_DATA_DIR = ROOT / "mock_data"
INDEX_PATH = DATA_DIR / "index.json"

# Retrieval
TOP_K = int(os.getenv("TOP_K", "4"))

# Coarse first-layer guardrail. A question whose distinctive words barely appear
# anywhere in the corpus is refused before the model is called at all; borderline
# cases are passed to the planner, which is instructed to refuse on weak evidence.
# See design-and-evaluation.md for how the two layers divide responsibility.
MIN_SUPPORT = float(os.getenv("MIN_SUPPORT", "0.34"))

# LLM planner. Absent an API key the agent falls back to deterministic routing,
# which keeps CI hermetic and the app runnable with no credentials at all.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
# GPT-5.6 Luna is the explicit cost-sensitive target for this project. The
# planner retains Chat Completions function tools, so it supplies the
# GPT-5.6-compatible ``reasoning_effort="none"`` option in app.planner.
# Override this only with a model your account can use and whose Chat
# Completions tool behavior you test.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "6"))
# A model can place more than one tool call in a single completion. Bound the
# total dispatches as well as the number of planner turns so a single response
# cannot bypass the turn limit and drive unbounded cost or MCP work.
MAX_TOOL_CALLS = int(os.getenv("MAX_TOOL_CALLS", "12"))
# Bound external/provider and local-tool waits so one stalled dependency cannot
# hold an HTTP request forever on a small free-tier service.
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "35"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))
MCP_OPERATION_TIMEOUT_SECONDS = float(os.getenv("MCP_OPERATION_TIMEOUT_SECONDS", "12"))
MCP_SHUTDOWN_TIMEOUT_SECONDS = float(os.getenv("MCP_SHUTDOWN_TIMEOUT_SECONDS", "10"))


def openai_api_key() -> str:
    """Read the current host key while retaining a test-friendly module default."""
    return os.getenv("OPENAI_API_KEY", OPENAI_API_KEY)


def llm_enabled() -> bool:
    """True when a key is configured, so the planner path can be used."""
    return bool(openai_api_key())


def expose_planner_errors() -> bool:
    """Opt-in diagnostics for a failing LLM planner.

    Off by default: a public demo should not return provider error text to an
    anonymous caller. Turn it on temporarily in the host environment to find out
    why the planner is degrading, then turn it off again.
    """
    return os.getenv("EXPOSE_PLANNER_ERRORS", "").strip().lower() in {"1", "true", "yes", "on"}
