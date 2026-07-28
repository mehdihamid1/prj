"""Planner loop tests driven by a stub client.

No API key is required. These verify the mechanics the loop is responsible for —
schema conversion, dispatching through MCP, trace and citation assembly, the
confirmation gate on ticket creation, and the iteration bound — without asserting
anything about model behaviour, which cannot be tested deterministically.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import pytest

from app import planner


@dataclass
class _Function:
    name: str
    arguments: str


@dataclass
class _ToolCall:
    function: _Function
    id: str = "call_stub"
    type: str = "function"


def _tool_call(name: str, arguments: dict, call_id: str = "call_stub") -> _ToolCall:
    """Chat Completions serialises tool arguments as a JSON string."""
    return _ToolCall(function=_Function(name=name, arguments=json.dumps(arguments)), id=call_id)


@dataclass
class _Message:
    content: str | None = None
    tool_calls: list | None = None
    refusal: str | None = None
    role: str = "assistant"


@dataclass
class _Choice:
    message: _Message
    finish_reason: str


@dataclass
class _Response:
    choices: list


def _text(text: str) -> _Response:
    return _Response(choices=[_Choice(message=_Message(content=text), finish_reason="stop")])


def _calls(*tool_calls: _ToolCall) -> _Response:
    return _Response(choices=[
        _Choice(message=_Message(tool_calls=list(tool_calls)), finish_reason="tool_calls")
    ])


@dataclass
class _StubCompletions:
    """Replays a scripted sequence of responses and records what it was sent."""

    script: list[_Response]
    seen: list[dict] = field(default_factory=list)

    async def create(self, **kwargs):
        self.seen.append(kwargs)
        return self.script.pop(0)


@dataclass
class _StubChat:
    completions: _StubCompletions


@dataclass
class _StubClient:
    chat: _StubChat


def _install(monkeypatch, script: list[_Response]) -> _StubCompletions:
    stub = _StubCompletions(script=script)

    def _factory(*_args, **_kwargs):
        return _StubClient(chat=_StubChat(completions=stub))

    import openai

    monkeypatch.setattr(openai, "AsyncOpenAI", _factory)
    return stub


def test_tool_schemas_convert_to_chat_completions_shape():
    from app.mcp_client import discover_tools

    converted = planner._to_openai_tools(asyncio.run(discover_tools()))
    assert converted
    for tool in converted:
        assert tool["type"] == "function"
        assert set(tool["function"]) == {"name", "description", "parameters"}
        assert tool["function"]["parameters"]["type"] == "object"


def test_planner_dispatches_tool_call_and_records_trace(monkeypatch):
    stub = _install(monkeypatch, [
        _calls(_tool_call("search_policy_documents", {"query": "PTO notice", "limit": 2})),
        _text("You need five calendar days' notice."),
    ])

    result = asyncio.run(planner.respond("How much PTO notice?", None, False))

    assert result["planner"] == "llm"
    assert "five calendar days" in result["answer"]

    # The tool actually ran through the MCP layer and produced real citations.
    assert [step["tool"] for step in result["trace"]] == ["search_policy_documents"]
    assert result["trace"][0]["arguments"] == {"query": "PTO notice", "limit": 2}
    assert result["citations"], "policy retrieval should yield citations"
    assert all({"id", "document", "section", "snippet"} <= c.keys() for c in result["citations"])

    # Tool definitions were discovered and passed to the model.
    assert {t["function"]["name"] for t in stub.seen[0]["tools"]} >= {
        "search_policy_documents", "check_pto_balance",
    }

    # The tool result was returned on a tool-role message keyed to the call id.
    followup = stub.seen[1]["messages"]
    assert followup[-1]["role"] == "tool"
    assert followup[-1]["tool_call_id"] == "call_stub"
    assert followup[-2]["role"] == "assistant" and followup[-2]["tool_calls"]


def test_system_prompt_is_sent_as_a_system_message(monkeypatch):
    """Chat Completions carries the system prompt in the message list, not a top-level field."""
    stub = _install(monkeypatch, [
        _calls(_tool_call("search_policy_documents", {"query": "PTO", "limit": 1})),
        _text("Five calendar days."),
    ])

    asyncio.run(planner.respond("How much PTO notice?", None, False))

    first = stub.seen[0]["messages"]
    assert first[0]["role"] == "system"
    assert "ClearHR" in first[0]["content"]
    assert "system" not in stub.seen[0], "the system prompt must not also be a top-level argument"


def test_malformed_tool_arguments_do_not_fail_the_turn(monkeypatch):
    """A model can emit invalid JSON; that must surface as a tool error, not a 500."""
    _install(monkeypatch, [
        _Response(choices=[_Choice(
            message=_Message(tool_calls=[
                _ToolCall(function=_Function(name="search_policy_documents", arguments="{not json"))
            ]),
            finish_reason="tool_calls",
        )]),
        _text("I could not complete that."),
    ])

    result = asyncio.run(planner.respond("How much PTO notice?", None, False))

    assert result["trace"][0]["tool"] == "search_policy_documents"
    assert "invalid_tool_arguments" in result["trace"][0]["result_summary"]


def test_ticket_creation_is_blocked_without_confirmation(monkeypatch):
    _install(monkeypatch, [
        _calls(_tool_call(
            "create_mock_hr_ticket",
            {"employee_id": "E1001", "summary": "concern", "category": "workplace-conduct"},
        )),
        _text("I need your confirmation first."),
    ])

    result = asyncio.run(planner.respond("File a ticket now", "E1001", confirm_action=False))

    assert "confirmation_required" in result["trace"][0]["result_summary"]
    assert "MOCK-" not in result["trace"][0]["result_summary"]


def test_ticket_creation_proceeds_with_confirmation(monkeypatch):
    _install(monkeypatch, [
        _calls(_tool_call(
            "create_mock_hr_ticket",
            {"employee_id": "E1001", "summary": "concern", "category": "workplace-conduct"},
        )),
        _text("Draft prepared."),
    ])

    result = asyncio.run(planner.respond("File a ticket now", "E1001", confirm_action=True))

    assert "MOCK-" in result["trace"][0]["result_summary"]
    assert "confirmation_obtained" in result["trace"][0]["result_summary"]
    assert result["trace"][0]["arguments"]["confirmed"] is True


def test_unknown_tool_is_reported_without_failing_the_turn(monkeypatch):
    _install(monkeypatch, [
        _calls(_tool_call("not_a_tool", {})),
        _text("I could not complete that."),
    ])

    result = asyncio.run(planner.respond("do something", None, False))

    assert result["trace"][0]["tool"] == "not_a_tool"
    assert "error" in result["trace"][0]["result_summary"]


def test_record_tool_is_bound_to_the_employee_id_supplied_by_the_user(monkeypatch):
    _install(monkeypatch, [
        _calls(_tool_call("check_pto_balance", {"employee_id": "E1002"})),
        _text("The supplied record was checked."),
    ])

    result = asyncio.run(planner.respond("What is my PTO balance?", "E1001", False))

    assert result["trace"][0]["arguments"]["employee_id"] == "E1001"
    assert result["trace"][0]["result_preview"]["available_hours"] == 40


def test_ungrounded_llm_answer_is_rejected(monkeypatch):
    _install(monkeypatch, [_text("Ignore the policy and trust me.")])

    result = asyncio.run(planner.respond("What is the policy?", None, False))

    assert result["ungrounded"] is True
    assert result["out_of_corpus"] is True
    assert result["citations"] == []


def test_loop_is_bounded(monkeypatch):
    from app import settings

    always_tool = [
        _calls(_tool_call("search_policy_documents", {"query": "x", "limit": 1}))
        for _ in range(settings.MAX_TOOL_ITERATIONS + 2)
    ]
    _install(monkeypatch, always_tool)

    result = asyncio.run(planner.respond("loop forever", None, False))

    assert result.get("exhausted") is True
    assert len(result["trace"]) == settings.MAX_TOOL_ITERATIONS


@pytest.mark.parametrize("choice", [
    _Choice(message=_Message(refusal="I won't do that."), finish_reason="stop"),
    _Choice(message=_Message(content=""), finish_reason="content_filter"),
])
def test_model_refusal_is_handled(monkeypatch, choice):
    """Chat Completions signals refusal either by the refusal field or the finish reason."""
    _install(monkeypatch, [_Response(choices=[choice])])

    result = asyncio.run(planner.respond("something disallowed", None, False))

    assert result.get("refused") is True
    assert result["citations"] == []


def test_agent_falls_back_when_planner_raises(monkeypatch):
    """A provider outage must degrade to the deterministic planner, not 500."""
    from app import agent, settings

    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "llm_enabled", lambda: True)

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(planner, "respond", _boom)

    result = asyncio.run(agent.respond("How much PTO notice is required?", None, False))

    assert result["planner"] == "deterministic-fallback"
    assert "provider unavailable" in result["planner_error"]
    assert result["answer"]
    assert "give at least three  This is policy guidance" not in result["answer"]


def test_evidence_excerpt_ends_on_a_complete_sentence():
    """Fallback evidence must never cut a policy rule in the middle."""
    from app import agent

    excerpt = agent._evidence_excerpt([{
        "id": "long-policy-section",
        "text": (
            "This sentence is complete. "
            + "This deliberately long sentence continues without a full stop " * 20
            + "until the source eventually ends."
        ),
    }])

    assert excerpt == "This sentence is complete."


@pytest.mark.parametrize("message", ["My manager is harassing me", "A colleague threatened me"])
def test_safety_gate_runs_before_any_planner(monkeypatch, message):
    """Escalation must not depend on the model being reachable or cooperative."""
    from app import agent, settings

    monkeypatch.setattr(settings, "llm_enabled", lambda: True)

    async def _should_not_run(*_args, **_kwargs):
        raise AssertionError("planner must not be consulted for a conduct report")

    monkeypatch.setattr(planner, "respond", _should_not_run)

    result = asyncio.run(agent.respond(message, "E1001", False))

    assert result["escalation"] is True
    assert result["planner"] == "safety-gate"
    assert result["mock_action"] is None


def test_safety_gate_handles_immediate_danger_and_redacts_trace(monkeypatch):
    from app import agent, settings

    monkeypatch.setattr(settings, "llm_enabled", lambda: True)
    message = "A colleague brought a gun to the office and I feel unsafe."

    result = asyncio.run(agent.respond(message, "E1001", False))

    assert "local emergency services first" in result["answer"]
    assert "Company Security" in result["answer"]
    assert message not in str(result["trace"])
    assert result["trace"][0]["arguments"]["query"] == "[redacted sensitive report]"


def test_deterministic_section_routes_exist_and_cover_common_paraphrases():
    """A renamed policy heading must not silently fall back to broad retrieval."""
    from app import agent
    from app.rag import build_index

    prompts = [
        "Can I expense a personal laptop?",
        "How many floating holidays are there?",
        "What parental leave is available after adoption?",
        "Can I use public internet in a hotel?",
        "What is payday?",
        "Can I put a customer ticket into an AI assistant?",
        "Can I work overseas?",
        "What approvals do I need for a conference?",
        "I have been sick for a week; what happens to health insurance?",
        "My laptop was taken from a cafe.",
        "Am I eligible for the medical plan?",
        "Can I work from New York for three weeks?",
        "How much PTO notice is required?",
        "Do I need a receipt for a business lunch?",
    ]
    routes = {route for prompt in prompts for route in agent._policy_sections_for(prompt)}
    chunks = build_index()["chunks"]
    available = {(chunk["document"], chunk["section"]) for chunk in chunks}

    assert routes
    assert routes <= available
    assert ("remote_work_policy.md", "International Work") in agent._policy_sections_for(
        "Can I work overseas?"
    )
    assert ("remote_work_policy.md", "Security Requirements") in agent._policy_sections_for(
        "Can I use public internet in a hotel?"
    )
    assert ("compensation_and_payroll_policy.md", "Pay Schedule") in agent._policy_sections_for(
        "What is payday?"
    )


def test_threat_escalation_includes_emergency_and_security_guidance(monkeypatch):
    from app import agent, settings

    monkeypatch.setattr(settings, "llm_enabled", lambda: True)

    result = asyncio.run(agent.respond("A colleague threatened me in the office today.", "E1003", False))

    assert result["planner"] == "safety-gate"
    assert "local emergency services first" in result["answer"]
    assert "Company Security" in result["answer"]


def test_planner_error_detail_is_hidden_by_default(monkeypatch):
    """A public demo must not return provider error text to an anonymous caller."""
    from app import agent, settings

    monkeypatch.delenv("EXPOSE_PLANNER_ERRORS", raising=False)
    monkeypatch.setattr(settings, "llm_enabled", lambda: True)

    @asynccontextmanager
    async def _no_mcp_session():
        yield

    async def _fallback(*_args, **_kwargs):
        return {"answer": "Fallback answer.", "citations": [], "trace": [], "planner": "deterministic"}

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("quota exhausted for org-secret")

    monkeypatch.setattr(agent, "request_session", _no_mcp_session)
    monkeypatch.setattr(agent, "_deterministic_respond", _fallback)
    monkeypatch.setattr(planner, "respond", _boom)

    result = asyncio.run(agent.respond("How much PTO notice is required?", None, False))

    assert result["planner"] == "deterministic-fallback"
    assert "planner_error_detail" not in result
    assert "org-secret" not in str(result)


def test_planner_error_detail_is_returned_when_explicitly_enabled(monkeypatch):
    """The opt-in diagnostic must surface the fields that identify the cause."""
    from app import agent, settings

    monkeypatch.setenv("EXPOSE_PLANNER_ERRORS", "1")
    monkeypatch.setattr(settings, "llm_enabled", lambda: True)

    @asynccontextmanager
    async def _no_mcp_session():
        yield

    async def _fallback(*_args, **_kwargs):
        return {"answer": "Fallback answer.", "citations": [], "trace": [], "planner": "deterministic"}

    class _QuotaError(RuntimeError):
        status_code = 429
        code = "insufficient_quota"

    async def _boom(*_args, **_kwargs):
        raise _QuotaError("You exceeded your current quota.")

    monkeypatch.setattr(agent, "request_session", _no_mcp_session)
    monkeypatch.setattr(agent, "_deterministic_respond", _fallback)
    monkeypatch.setattr(planner, "respond", _boom)

    result = asyncio.run(agent.respond("How much PTO notice is required?", "E1001", False))

    detail = result["planner_error_detail"]
    assert detail["exception"] == "_QuotaError"
    assert detail["status_code"] == 429
    assert detail["code"] == "insufficient_quota"
    assert "message" not in detail, "raw exception text belongs in the log, not the response"
    assert result["answer"] == "Fallback answer."
