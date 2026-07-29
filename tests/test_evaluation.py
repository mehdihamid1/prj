"""Focused tests for the deterministic evaluation harness."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from evaluation import run_eval


def _case(**overrides: Any) -> dict[str, Any]:
    case = {
        "id": "case",
        "type": "policy",
        "question": "What is the PTO notice period?",
        "expected": "Employees need five calendar days of notice.",
        "rubric": {"required": [["five calendar days"]]},
        "expected_documents": ["pto_policy.md"],
        "expected_tools": ["search_policy_documents"],
        "expected_behavior": "answer_with_citation",
    }
    case.update(overrides)
    return case


def _result(**overrides: Any) -> dict[str, Any]:
    result = {
        "answer": "Employees need five calendar days of notice.",
        "citations": [
            {
                "id": "pto-1",
                "document": "pto_policy.md",
                "section": "Request and Approval",
                "snippet": "Submit planned PTO at least five calendar days ahead.",
            }
        ],
        "trace": [{"tool": "search_policy_documents", "arguments": {}}],
        "planner": "deterministic",
        "_latency_ms": 1.0,
    }
    result.update(overrides)
    return result


def test_multi_document_citation_requires_all_declared_documents():
    case = _case(expected_documents=["remote_work_policy.md", "data_security_policy.html"])
    result = _result(citations=[
        {
            "id": "remote-1",
            "document": "remote_work_policy.md",
            "section": "International Work",
            "snippet": "Approval is required.",
        }
    ])

    row = run_eval.score_case(case, result, {"remote-1"})

    assert row["citation_document_recall"] == 0.5
    assert row["citation_coverage_ok"] is False
    assert row["citation_ok"] is False


def test_answer_rubric_blocks_a_generic_but_well_cited_answer():
    result = _result(answer="Please consult the PTO policy.")

    row = run_eval.score_case(_case(), result, {"pto-1"})

    assert row["citation_ok"] is True
    assert row["tool_ok"] is True
    assert row["answer_content_ok"] is False
    assert row["overall_ok"] is False


def test_gold_expected_answer_contributes_to_the_content_score():
    case = _case(rubric={"required": [["pto policy"]]})
    result = _result(answer="Please see the PTO policy.")

    row = run_eval.score_case(case, result, {"pto-1"})

    assert row["rubric_ok"] is True
    assert row["reference_term_recall"] == 0
    assert row["answer_content_ok"] is False


def test_confirmed_mock_action_is_scored_as_a_positive_safe_workflow():
    case = _case(
        type="action-confirmed",
        expected="After confirmation, create a mock HR ticket and route it to People Operations.",
        rubric={"required": [["mock hr ticket", "mock ticket"], ["people operations"]]},
        expected_documents=["workplace_conduct_policy.md"],
        expected_tools=["search_policy_documents", "create_mock_hr_ticket"],
        expected_behavior="action_taken",
        confirm_mock_action=True,
    )
    result = _result(
        answer="A mock HR ticket was created and routed to People Operations.",
        citations=[
            {
                "id": "conduct-1",
                "document": "workplace_conduct_policy.md",
                "section": "Reporting Concerns",
                "snippet": "Route reports to People Operations.",
            }
        ],
        trace=[
            {"tool": "search_policy_documents", "arguments": {}},
            {"tool": "create_mock_hr_ticket", "arguments": {}},
        ],
        mock_action={"ticket_id": "MOCK-1001"},
    )

    row = run_eval.score_case(case, result, {"conduct-1"})

    assert row["observed_behavior"] == "action_taken"
    assert row["action_created"] is True
    assert row["action_ok"] is True
    assert row["overall_ok"] is True


class _FakeResponse:
    status_code = 200
    is_success = True

    def json(self) -> dict[str, Any]:
        return _result()


class _FakeClient:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def post(self, path: str, json: dict[str, Any]) -> _FakeResponse:
        self.requests.append((path, json))
        return _FakeResponse()


def test_base_url_mode_posts_chat_payload_and_reports_http_latency(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(run_eval.httpx, "AsyncClient", lambda **_kwargs: fake_client)
    case = _case(employee_id="E1001", confirm_mock_action=True)

    rows = asyncio.run(run_eval.run_once([case], base_url="https://clearhr.example/"))
    summary = run_eval.summarise(rows, base_url="https://clearhr.example")

    assert fake_client.requests == [
        ("/chat", {
            "message": case["question"],
            "employee_id": "E1001",
            "confirm_mock_action": True,
        })
    ]
    assert rows[0]["http_status"] == 200
    assert rows[0]["citations_resolve"] is None
    assert rows[0]["latency_ms"] >= 0
    assert summary["mode"] == "http"
    assert summary["http_success"] == "1/1 (100%)"


def test_artifacts_include_synthetic_answer_and_trace_for_human_review(tmp_path):
    row = run_eval.score_case(_case(), _result(), {"pto-1"})
    path = tmp_path / "artifacts.json"

    run_eval.write_artifacts([row], path)

    saved = json.loads(path.read_text())
    artifact = saved["cases"][0]
    assert "Synthetic evaluation artifacts" in saved["notice"]
    assert artifact["answer"] == "Employees need five calendar days of notice."
    assert artifact["citations"][0]["id"] == "pto-1"
    assert artifact["trace"][0]["tool"] == "search_policy_documents"


def test_retrieval_ablation_reports_strict_multi_document_coverage(monkeypatch):
    cases = [
        _case(id="one", expected_documents=["pto_policy.md"]),
        _case(
            id="two",
            question="What applies to overseas work?",
            expected_documents=["remote_work_policy.md", "data_security_policy.html"],
        ),
    ]

    def fake_search(question: str, _limit: int):
        if question == cases[0]["question"]:
            return [{"document": "pto_policy.md"}, {"document": "expense_policy.md"}]
        return [
            {"document": "remote_work_policy.md"},
            {"document": "remote_work_policy.md"},
        ]

    monkeypatch.setattr(run_eval, "search", fake_search)
    row = run_eval.retrieval_ablation(cases, ks=(2,))[0]

    assert row["recall"] == "2/2 (100%)"
    assert row["expected_document_recall"] == "2/3 (67%)"
    assert row["complete_coverage"] == "1/2 (50%)"
    # Repeated remote-work chunks are one retrieved document, not two precise hits.
    assert row["document_precision"] == "2/3 (67%)"
