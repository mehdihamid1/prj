"""Safe, explainable agent orchestration with concise operational traces.

Planning is intentionally deterministic for a reproducible first draft. An LLM
planner can be introduced later without changing the MCP boundary.
"""
from __future__ import annotations

from typing import Any

from .mcp_client import call

SENSITIVE = ("harass", "discriminat", "retaliat", "assault", "threat", "unsafe")


def _cite(results: list[dict]) -> list[dict]:
    return [{"id": x["id"], "document": x["document"], "section": x["section"], "snippet": x["text"][:240]} for x in results]


async def respond(message: str, employee_id: str | None = None, confirm_action: bool = False) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []

    async def tool(name: str, arguments: dict[str, Any]) -> Any:
        output = await call(name, arguments)
        trace.append({"tool": name, "arguments": arguments, "result_summary": str(output)[:360]})
        return output

    normalized = message.lower()
    if any(word in normalized for word in SENSITIVE):
        policies = await tool("search_policy_documents", {"query": "workplace conduct reporting non-retaliation", "limit": 3})
        ticket = None
        if employee_id and confirm_action:
            ticket = await tool("create_mock_hr_ticket", {"employee_id": employee_id, "category": "workplace-conduct", "summary": message[:300]})
        action = "A draft mock case was prepared; confirm it with HR before any submission." if ticket else "I can prepare a mock HR case only after you explicitly confirm."
        return {"answer": f"I’m sorry this is happening. This needs confidential HR triage rather than a policy-only answer. {action}", "citations": _cite(policies), "trace": trace, "escalation": True, "mock_action": ticket}

    if not employee_id and any(word in normalized for word in ("my pto", "my benefit", "am i eligible", "i take")):
        return {"answer": "Please provide a synthetic employee ID (for example E1001) so I can check the mock record. I will not guess identity or eligibility.", "citations": [], "trace": trace, "needs_clarification": True}

    policy_query = message
    policy = await tool("search_policy_documents", {"query": policy_query, "limit": 4})
    facts: list[str] = []

    if employee_id and any(word in normalized for word in ("pto", "vacation", "time off", "days off")):
        profile = await tool("lookup_employee_profile", {"employee_id": employee_id})
        balance = await tool("check_pto_balance", {"employee_id": employee_id})
        if "error" in balance:
            return {"answer": "I could not find that employee’s PTO record. Please verify the synthetic employee ID.", "citations": _cite(policy), "trace": trace}
        facts.append(f"Your mock record shows {balance['available_hours']} available PTO hours ({balance['available_hours'] / 8:g} workdays), with {profile.get('manager_name', 'your manager')} listed as manager.")

    if employee_id and any(word in normalized for word in ("benefit", "medical", "insurance", "401", "eligible")):
        profile = await tool("lookup_employee_profile", {"employee_id": employee_id})
        benefit = await tool("lookup_benefits_status", {"employee_id": employee_id})
        facts.append(f"Mock profile: {profile.get('employment_type', 'unknown')} employee; benefits status: {benefit.get('status', 'not found')}, plans: {', '.join(benefit.get('plans', [])) or 'none'}.")

    if not policy or policy[0]["score"] < 0.05:
        return {"answer": "I don’t have enough evidence in the internal policy corpus to answer that safely. Please contact HR or ask about a documented policy topic.", "citations": [], "trace": trace, "out_of_corpus": True}

    evidence = " ".join(item["text"].replace("\n", " ") for item in policy[:2])
    answer = " ".join(facts + [f"Based on the policy evidence: {evidence[:700]}", "This is policy guidance, not legal, tax, or medical advice; HR can confirm exceptions."])
    return {"answer": answer, "citations": _cite(policy), "trace": trace, "answer_basis": "MCP policy retrieval" + (" + synthetic employee data" if facts else "")}
