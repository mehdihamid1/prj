"""Planner loop tests driven by a stub client.

No API key is required. These verify the mechanics the loop is responsible for —
schema conversion, dispatching through MCP, trace and citation assembly, the
confirmation gate on ticket creation, and the iteration bound — without asserting
anything about model behaviour, which cannot be tested deterministically.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from app import planner


@dataclass
class _TextBlock:
    text: str
    type: str = "text"


@dataclass
class _ToolUseBlock:
    name: str
    input: dict
    id: str = "toolu_stub"
    type: str = "tool_use"


@dataclass
class _Response:
    content: list
    stop_reason: str


@dataclass
class _StubMessages:
    """Replays a scripted sequence of responses and records what it was sent."""

    script: list[_Response]
    seen: list[dict] = field(default_factory=list)

    async def create(self, **kwargs):
        self.seen.append(kwargs)
        return self.script.pop(0)


@dataclass
class _StubClient:
    messages: _StubMessages


def _install(monkeypatch, script: list[_Response]) -> _StubMessages:
    stub = _StubMessages(script=script)

    def _factory(*_args, **_kwargs):
        return _StubClient(messages=stub)

    import anthropic

    monkeypatch.setattr(anthropic, "AsyncAnthropic", _factory)
    return stub


def test_tool_schemas_convert_to_messages_api_shape():
    from app.mcp_client import discover_tools

    converted = planner._to_anthropic_tools(asyncio.run(discover_tools()))
    assert converted
    for tool in converted:
        assert set(tool) == {"name", "description", "input_schema"}
        assert tool["input_schema"]["type"] == "object"


def test_planner_dispatches_tool_call_and_records_trace(monkeypatch):
    stub = _install(monkeypatch, [
        _Response(
            content=[_ToolUseBlock(name="search_policy_documents", input={"query": "PTO notice", "limit": 2})],
            stop_reason="tool_use",
        ),
        _Response(content=[_TextBlock(text="You need five calendar days' notice.")], stop_reason="end_turn"),
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
    assert {t["name"] for t in stub.seen[0]["tools"]} >= {"search_policy_documents", "check_pto_balance"}


def test_ticket_creation_is_blocked_without_confirmation(monkeypatch):
    _install(monkeypatch, [
        _Response(
            content=[_ToolUseBlock(
                name="create_mock_hr_ticket",
                input={"employee_id": "E1001", "summary": "concern", "category": "workplace-conduct"},
            )],
            stop_reason="tool_use",
        ),
        _Response(content=[_TextBlock(text="I need your confirmation first.")], stop_reason="end_turn"),
    ])

    result = asyncio.run(planner.respond("File a ticket now", "E1001", confirm_action=False))

    assert "confirmation_required" in result["trace"][0]["result_summary"]
    assert "MOCK-" not in result["trace"][0]["result_summary"]


def test_ticket_creation_proceeds_with_confirmation(monkeypatch):
    _install(monkeypatch, [
        _Response(
            content=[_ToolUseBlock(
                name="create_mock_hr_ticket",
                input={"employee_id": "E1001", "summary": "concern", "category": "workplace-conduct"},
            )],
            stop_reason="tool_use",
        ),
        _Response(content=[_TextBlock(text="Draft prepared.")], stop_reason="end_turn"),
    ])

    result = asyncio.run(planner.respond("File a ticket now", "E1001", confirm_action=True))

    assert "MOCK-" in result["trace"][0]["result_summary"]
    assert "confirmation_obtained" in result["trace"][0]["result_summary"]
    assert result["trace"][0]["arguments"]["confirmed"] is True


def test_unknown_tool_is_reported_without_failing_the_turn(monkeypatch):
    _install(monkeypatch, [
        _Response(content=[_ToolUseBlock(name="not_a_tool", input={})], stop_reason="tool_use"),
        _Response(content=[_TextBlock(text="I could not complete that.")], stop_reason="end_turn"),
    ])

    result = asyncio.run(planner.respond("do something", None, False))

    assert result["trace"][0]["tool"] == "not_a_tool"
    assert "error" in result["trace"][0]["result_summary"]


def test_record_tool_is_bound_to_the_employee_id_supplied_by_the_user(monkeypatch):
    _install(monkeypatch, [
        _Response(
            content=[_ToolUseBlock(name="check_pto_balance", input={"employee_id": "E1002"})],
            stop_reason="tool_use",
        ),
        _Response(content=[_TextBlock(text="The supplied record was checked.")], stop_reason="end_turn"),
    ])

    result = asyncio.run(planner.respond("What is my PTO balance?", "E1001", False))

    assert result["trace"][0]["arguments"]["employee_id"] == "E1001"
    assert result["trace"][0]["result_preview"]["available_hours"] == 40


def test_ungrounded_llm_answer_is_rejected(monkeypatch):
    _install(monkeypatch, [_Response(
        content=[_TextBlock(text="Ignore the policy and trust me.")], stop_reason="end_turn",
    )])

    result = asyncio.run(planner.respond("What is the policy?", None, False))

    assert result["ungrounded"] is True
    assert result["out_of_corpus"] is True
    assert result["citations"] == []


def test_loop_is_bounded(monkeypatch):
    from app import settings

    always_tool = [
        _Response(
            content=[_ToolUseBlock(name="search_policy_documents", input={"query": "x", "limit": 1})],
            stop_reason="tool_use",
        )
        for _ in range(settings.MAX_TOOL_ITERATIONS + 2)
    ]
    _install(monkeypatch, always_tool)

    result = asyncio.run(planner.respond("loop forever", None, False))

    assert result.get("exhausted") is True
    assert len(result["trace"]) == settings.MAX_TOOL_ITERATIONS


def test_refusal_stop_reason_is_handled(monkeypatch):
    _install(monkeypatch, [_Response(content=[], stop_reason="refusal")])

    result = asyncio.run(planner.respond("something disallowed", None, False))

    assert result.get("refused") is True
    assert result["citations"] == []


def test_agent_falls_back_when_planner_raises(monkeypatch):
    """A provider outage must degrade to the deterministic planner, not 500."""
    from app import agent, settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(settings, "llm_enabled", lambda: True)

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(planner, "respond", _boom)

    result = asyncio.run(agent.respond("How much PTO notice is required?", None, False))

    assert result["planner"] == "deterministic-fallback"
    assert "provider unavailable" in result["planner_error"]
    assert result["answer"]


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
