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
    assert json.loads(result.body) == {"status": "unavailable", "mcp_connected": False}
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
