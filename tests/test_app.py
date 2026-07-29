import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app import main


def _request(client: str = "203.0.113.10") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/chat",
            "headers": [],
            "client": (client, 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


@pytest.fixture(autouse=True)
def clear_rate_limit() -> None:
    main._reset_chat_rate_limit()
    yield
    main._reset_chat_rate_limit()


def test_health_returns_safe_503_when_mcp_is_unavailable(monkeypatch):
    async def unavailable():
        raise RuntimeError("MCP startup failed: internal-token-value")

    monkeypatch.setattr(main, "discover_tools", unavailable)

    result = asyncio.run(main.health())

    assert isinstance(result, JSONResponse)
    assert result.status_code == 503
    body = json.loads(result.body)
    assert body["status"] == "unavailable"
    assert body["mcp_connected"] is False
    # The degraded body may carry non-secret deployment facts such as the active
    # retriever, but never the exception text, which can name internal detail.
    assert set(body) <= {
        "status", "mcp_connected", "rag_backend", "configured_rag_backend",
    }
    assert b"internal-token-value" not in result.body


def test_chat_rate_limit_returns_429_and_retry_after(monkeypatch):
    async def successful_response(*_args):
        return {"answer": "Synthetic answer"}

    monkeypatch.setattr(main, "respond", successful_response)
    monkeypatch.setattr(main, "CHAT_RATE_LIMIT", 2)
    monkeypatch.setattr(main, "GLOBAL_CHAT_RATE_LIMIT", 20)
    payload = main.ChatRequest(message="Can I take PTO?")

    for _ in range(2):
        response = Response()
        assert asyncio.run(main.chat(payload, _request(), response))["answer"] == "Synthetic answer"
        assert response.headers["cache-control"] == "no-store"

    with pytest.raises(HTTPException) as raised:
        asyncio.run(main.chat(payload, _request(), Response()))

    assert raised.value.status_code == 429
    assert raised.value.detail == "Too many requests. Please wait and try again."
    assert int(raised.value.headers["Retry-After"]) >= 1
    assert raised.value.headers["Cache-Control"] == "no-store"


def test_chat_forwards_explicit_mock_confirmation(monkeypatch):
    received: dict[str, object] = {}

    async def capture(message: str, employee_id: str | None, confirm_action: bool):
        received.update(
            message=message,
            employee_id=employee_id,
            confirm_action=confirm_action,
        )
        return {"answer": "Mock draft prepared"}

    monkeypatch.setattr(main, "respond", capture)
    payload = main.ChatRequest(
        message="Please help with a workplace concern.",
        employee_id="E1001",
        confirm_mock_action=True,
    )

    result = asyncio.run(main.chat(payload, _request(), Response()))

    assert result["answer"] == "Mock draft prepared"
    assert received == {
        "message": "Please help with a workplace concern.",
        "employee_id": "E1001",
        "confirm_action": True,
    }


def test_chat_hides_backend_exception_details(monkeypatch):
    async def unavailable(*_args):
        raise RuntimeError("provider secret: do-not-return-this")

    monkeypatch.setattr(main, "respond", unavailable)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            main.chat(main.ChatRequest(message="Can I take PTO?"), _request(), Response())
        )

    assert raised.value.status_code == 503
    assert raised.value.detail == "The HR tool service is temporarily unavailable. Please retry."
    assert "do-not-return-this" not in str(raised.value.detail)


def test_demo_page_marks_data_as_synthetic_and_sends_confirmation():
    page = (Path(main.__file__).parent / "static" / "index.html").read_text()

    assert "Synthetic demo only" in page
    assert "do not enter real personal information" in page
    assert 'id="confirm-mock-action"' in page
    assert "confirm_mock_action: confirmationInput.checked" in page
    assert "confirmationInput.checked = false" in page


def test_demo_page_includes_an_accurate_workflow_map():
    page = (Path(main.__file__).parent / "static" / "index.html").read_text()

    assert 'id="workflow-map"' in page
    assert "Agent orchestrator" in page
    assert "OpenAI LLM planner" in page
    assert "MCP client → FastMCP server" in page
    assert "Structured results return to the LLM" in page
    assert "final answer, citations, and exact MCP tool trace" in page


def test_health_reports_the_mcp_child_rag_backend(monkeypatch):
    """Health must query the child; a parent setting alone is not evidence."""
    from app import settings

    async def tools():
        return [{"name": "get_retrieval_status"}]

    async def child_status():
        return {
            "rag_backend": "dense",
            "index_backend": "dense",
            "rag_model": "BAAI/bge-small-en-v1.5",
            "rag_index": "index.dense.json",
            "rag_index_version": 5,
            "rag_chunks": 142,
            "rag_dimensions": 384,
            "rag_provider": "fastembed",
            "rag_storage": "local-json-dense-vector-index",
            "dense_encoder_loaded": True,
        }

    monkeypatch.setattr(settings, "rag_backend", lambda: "dense")
    monkeypatch.setattr(main, "discover_tools", tools)
    monkeypatch.setattr(main.mcp_client, "retrieval_status", child_status)

    payload = asyncio.run(main.health())

    assert payload["rag_backend"] == "dense"
    assert payload["configured_rag_backend"] == "dense"
    assert payload["rag_status_source"] == "mcp_child"
    assert payload["rag_model"] == "BAAI/bge-small-en-v1.5"
    assert payload["dense_encoder_loaded"] is True
    assert payload["status"] == "ok"


def test_health_returns_safe_503_when_parent_and_child_backend_disagree(monkeypatch):
    async def tools():
        return [{"name": "get_retrieval_status"}]

    async def child_status():
        return {"rag_backend": "lexical", "index_backend": "lexical"}

    monkeypatch.setattr(main.settings, "rag_backend", lambda: "dense")
    monkeypatch.setattr(main, "discover_tools", tools)
    monkeypatch.setattr(main.mcp_client, "retrieval_status", child_status)

    result = asyncio.run(main.health())

    assert isinstance(result, JSONResponse)
    assert result.status_code == 503
    assert json.loads(result.body) == {
        "status": "misconfigured",
        "mcp_connected": True,
        "rag_status_source": "mcp_child",
        "rag_backend": "lexical",
        "configured_rag_backend": "dense",
    }
