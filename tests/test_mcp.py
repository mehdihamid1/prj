import asyncio

from app.mcp_client import call, discover_tools

REQUIRED_TOOLS = {
    "search_policy_documents",
    "get_policy_section",
    "lookup_employee_profile",
    "check_pto_balance",
    "lookup_benefits_status",
    "create_mock_hr_ticket",
}


def test_mcp_discovers_required_tools():
    tools = asyncio.run(discover_tools())
    names = {tool["name"] for tool in tools}
    assert REQUIRED_TOOLS <= names


def test_discovered_tools_expose_usable_schemas():
    """The planner builds its tool definitions from these schemas, so they must be complete."""
    tools = asyncio.run(discover_tools())
    for tool in tools:
        assert tool["description"], f"{tool['name']} has no description"
        schema = tool["inputSchema"]
        assert schema["type"] == "object"
        assert "properties" in schema


def test_mcp_tool_call_returns_policy_evidence():
    """A real call through the MCP layer, not a direct call into app.rag."""
    result = asyncio.run(call("search_policy_documents", {"query": "PTO notice period", "limit": 3}))
    assert isinstance(result, list) and result
    top = result[0]
    assert {"id", "document", "section", "text", "score"} <= top.keys()


def test_mcp_tool_call_returns_structured_record():
    result = asyncio.run(call("check_pto_balance", {"employee_id": "E1001"}))
    assert result["available_hours"] == 40


def test_mcp_tool_call_handles_missing_record():
    """A missing ID returns a structured error rather than raising."""
    result = asyncio.run(call("lookup_employee_profile", {"employee_id": "E9999"}))
    assert result["error"] == "Employee not found"


def test_policy_section_does_not_expose_internal_embeddings():
    result = asyncio.run(call("get_policy_section", {
        "document": "workplace_conduct_policy.md", "section": "Reporting Concerns",
    }))
    assert result
    assert all("embedding" not in chunk for chunk in result)


def test_mock_ticket_tool_enforces_confirmation_and_known_employee():
    blocked = asyncio.run(call("create_mock_hr_ticket", {
        "employee_id": "E1001", "summary": "synthetic concern", "category": "workplace-conduct",
    }))
    assert blocked["error"] == "confirmation_required"

    draft = asyncio.run(call("create_mock_hr_ticket", {
        "employee_id": "E1001", "summary": "synthetic concern", "category": "workplace-conduct",
        "confirmed": True,
    }))
    assert draft["mock_only"] is True
    assert draft["confirmation_obtained"] is True


def test_one_server_process_serves_concurrent_calls():
    """The session is shared, not spawned per call.

    A process per request measured at ~590 ms and ~51 MB, which on a small
    container makes health probes fork an interpreter and a burst of traffic
    exhaust memory. This asserts the shared-session behaviour that replaced it.
    """
    from app import mcp_client

    async def scenario():
        await mcp_client.startup()
        first = await mcp_client.session()
        results = await asyncio.gather(
            *[mcp_client.call("check_pto_balance", {"employee_id": "E1001"}) for _ in range(10)]
        )
        same = await mcp_client.session() is first
        await mcp_client.shutdown()
        return results, same

    results, same_session = asyncio.run(scenario())
    assert all(item["available_hours"] == 40 for item in results)
    assert same_session, "every call must reuse the one initialised session"


def test_session_survives_shutdown_then_restart():
    """Lifespan shutdown must leave the module reusable, not wedged.

    The MCP context managers are anyio-based and must be exited on the task that
    entered them, which is why a supervisor task owns the session. Entering from
    one task and closing from another previously raised
    "Attempted to exit cancel scope in a different task".
    """
    from app import mcp_client

    async def scenario():
        await mcp_client.startup()
        await mcp_client.shutdown()
        assert mcp_client._session is None

        # Restart from a different task than the one that first opened it.
        async def restart():
            return await mcp_client.call("check_pto_balance", {"employee_id": "E1001"})

        result = await asyncio.create_task(restart())
        await mcp_client.shutdown()
        return result

    assert asyncio.run(scenario())["available_hours"] == 40
