import asyncio

from app.mcp_client import discover_tools


def test_mcp_discovers_required_tools():
    tools = asyncio.run(discover_tools())
    names = {tool["name"] for tool in tools}
    assert {"search_policy_documents", "lookup_employee_profile", "check_pto_balance", "create_mock_hr_ticket"} <= names
