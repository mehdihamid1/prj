from __future__ import annotations

import logging
import os
from collections import deque
from contextlib import asynccontextmanager
from math import ceil
from pathlib import Path
from threading import Lock
from time import monotonic

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from . import mcp_client, settings
from .agent import respond
from .mcp_client import discover_tools

logger = logging.getLogger(__name__)


def _positive_int_from_env(name: str, default: int) -> int:
    """Read a safe, positive demo setting without making boot fragile."""
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


# This is deliberately a small, process-local guard for a single-worker demo
# deployment. It limits expensive planner/tool work even if every request comes
# through the same hosting proxy. It is not a replacement for an edge/WAF
# limiter in a multi-instance production system.
CHAT_RATE_WINDOW_SECONDS = _positive_int_from_env("CHAT_RATE_WINDOW_SECONDS", 60)
# The default allows one complete 28-case deployment evaluation as well as a
# short demo, while still bounding an accidentally public endpoint.  It is a
# cost guard for this coursework service, not production-grade authentication.
CHAT_RATE_LIMIT = _positive_int_from_env("CHAT_RATE_LIMIT", 30)
GLOBAL_CHAT_RATE_LIMIT = _positive_int_from_env("GLOBAL_CHAT_RATE_LIMIT", 60)
_rate_limit_lock = Lock()
_chat_requests_by_client: dict[str, deque[float]] = {}
_all_chat_requests: deque[float] = deque()


def _prune_rate_limit_state(now: float) -> None:
    """Discard expired timestamps so the in-memory limiter stays bounded."""
    cutoff = now - CHAT_RATE_WINDOW_SECONDS
    while _all_chat_requests and _all_chat_requests[0] <= cutoff:
        _all_chat_requests.popleft()

    for client, timestamps in list(_chat_requests_by_client.items()):
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()
        if not timestamps:
            del _chat_requests_by_client[client]


def _retry_after_seconds(timestamps: deque[float], now: float) -> int:
    """Return a conservative whole-second retry time for a full window."""
    return max(1, ceil(CHAT_RATE_WINDOW_SECONDS - (now - timestamps[0])))


def _chat_rate_limit_retry_after(request: Request) -> int | None:
    """Reserve one chat request or return the required wait time.

    Do not trust a caller-controlled ``X-Forwarded-For`` header here. The
    process-wide cap still protects costs when a host proxy masks client IPs.
    """
    client = request.client.host if request.client else "unknown"
    now = monotonic()

    with _rate_limit_lock:
        _prune_rate_limit_state(now)
        timestamps = _chat_requests_by_client.setdefault(client, deque())
        retry_after: list[int] = []
        if len(timestamps) >= CHAT_RATE_LIMIT:
            retry_after.append(_retry_after_seconds(timestamps, now))
        if len(_all_chat_requests) >= GLOBAL_CHAT_RATE_LIMIT:
            retry_after.append(_retry_after_seconds(_all_chat_requests, now))
        if retry_after:
            return max(retry_after)

        timestamps.append(now)
        _all_chat_requests.append(now)
        return None


def _reset_chat_rate_limit() -> None:
    """Clear in-memory rate state (used by focused endpoint tests)."""
    with _rate_limit_lock:
        _chat_requests_by_client.clear()
        _all_chat_requests.clear()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The persistent MCP child owns RAG readiness.  In dense mode it is the
    # only process allowed to load the ONNX embedding model, avoiding a second
    # model copy in this web process on a 512 MB free-tier container.
    try:
        await mcp_client.startup()
    except Exception:
        # Keep the HTTP process alive long enough for /health to return a
        # meaningful 503. The client will retry the connection on later calls.
        logger.warning("MCP did not initialize at startup")
    try:
        yield
    finally:
        await mcp_client.shutdown()


app = FastAPI(title="ClearHR", version="0.1.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=3, max_length=3000)
    employee_id: str | None = Field(default=None, pattern=r"^E[0-9]{4}$")
    confirm_mock_action: bool = False


@app.exception_handler(RequestValidationError)
async def invalid_request(_: Request, __: RequestValidationError) -> JSONResponse:
    """Avoid echoing supplied text or IDs back in validation-error payloads."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": (
                "Invalid request. Provide a 3–3000 character message and, if needed, "
                "a synthetic employee ID in the form E0000."
            )
        },
        headers={"Cache-Control": "no-store"},
    )


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
async def health():
    try:
        tools = await discover_tools()
        child_status = await mcp_client.retrieval_status()
        configured_backend = settings.rag_backend()
        child_backend = child_status["rag_backend"]
        # Retrieval executes in the MCP child. A parent-only environment value
        # is not deployment evidence: it can disagree with the process that
        # actually answers policy questions. Fail the health check loudly on a
        # mismatch instead of reporting a misleading 200.
        if child_backend != configured_backend:
            logger.warning(
                "MCP child RAG backend mismatch: parent=%s child=%s",
                configured_backend,
                child_backend,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "misconfigured",
                    "mcp_connected": True,
                    "rag_status_source": "mcp_child",
                    "rag_backend": child_backend,
                    "configured_rag_backend": configured_backend,
                },
                headers={"Cache-Control": "no-store"},
            )

        # All fields are non-secret operational facts. `rag_backend` is the
        # value returned by the child, while `configured_rag_backend` makes a
        # future mismatch diagnosable without revealing provider credentials.
        return {
            "status": "ok",
            "mcp_connected": True,
            "rag_status_source": "mcp_child",
            "mcp_tool_count": len(tools),
            "rag_backend": child_backend,
            "configured_rag_backend": configured_backend,
            "rag_model": child_status.get("rag_model"),
            "rag_index": child_status.get("rag_index"),
            "rag_index_version": child_status.get("rag_index_version"),
            "rag_chunks": child_status.get("rag_chunks"),
            "rag_dimensions": child_status.get("rag_dimensions"),
            "rag_provider": child_status.get("rag_provider"),
            "rag_storage": child_status.get("rag_storage"),
            "dense_encoder_loaded": child_status.get("dense_encoder_loaded"),
            "planner_model": settings.OPENAI_MODEL,
        }
    except Exception:
        logger.warning("Health check could not reach the MCP service")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "mcp_connected": False,
                "rag_backend": settings.rag_backend(),
                "configured_rag_backend": settings.rag_backend(),
            },
            headers={"Cache-Control": "no-store"},
        )


@app.get("/tools")
async def tools() -> dict:
    try:
        return {"tools": await discover_tools()}
    except Exception:
        logger.warning("Tool discovery could not reach the MCP service")
        raise HTTPException(503, "The HR tool service is temporarily unavailable.") from None


@app.post("/chat")
async def chat(payload: ChatRequest, request: Request, response: Response) -> dict:
    retry_after = _chat_rate_limit_retry_after(request)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait and try again.",
            headers={"Retry-After": str(retry_after), "Cache-Control": "no-store"},
        )

    # The response can include synthetic employee details and an operational
    # trace, neither of which should be retained by a browser or intermediary.
    response.headers["Cache-Control"] = "no-store"
    try:
        return await respond(payload.message, payload.employee_id, payload.confirm_mock_action)
    except Exception:
        logger.warning("Chat request could not be completed")
        raise HTTPException(
            503,
            "The HR tool service is temporarily unavailable. Please retry.",
            headers={"Cache-Control": "no-store"},
        ) from None
