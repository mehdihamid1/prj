"""Verify MCP tool discovery and a live tool call over the stdio transport.

The deployed service likewise calls this server over stdio, but this script
verifies that boundary independently. It launches `python -m app.mcp_server` as
a separate process, speaks MCP to it over stdio, lists the tools, and calls one
— the evidence the project brief asks CI to provide.
"""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REQUIRED = {
    "search_policy_documents",
    "get_policy_section",
    "lookup_employee_profile",
    "check_pto_balance",
    "lookup_benefits_status",
    "create_mock_hr_ticket",
}


def _payload(result) -> object:
    """Prefer the structured result; fall back to parsing the text content."""
    if getattr(result, "structuredContent", None):
        structured = result.structuredContent
        return structured.get("result", structured)
    text = "".join(block.text for block in result.content if hasattr(block, "text"))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


async def main() -> None:
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"])

    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            missing = REQUIRED - names
            if missing:
                raise SystemExit(f"MCP server is missing required tools: {sorted(missing)}")
            print(f"Discovered {len(names)} MCP tools over stdio: {sorted(names)}")

            policy = _payload(await session.call_tool(
                "search_policy_documents", {"query": "PTO notice period", "limit": 2}
            ))
            if not isinstance(policy, list) or not policy:
                raise SystemExit(f"search_policy_documents returned no evidence: {policy!r}")
            print(f"search_policy_documents returned {len(policy)} chunks; top document: {policy[0]['document']}")

            balance = _payload(await session.call_tool("check_pto_balance", {"employee_id": "E1001"}))
            if not isinstance(balance, dict) or "available_hours" not in balance:
                raise SystemExit(f"check_pto_balance returned an unexpected payload: {balance!r}")
            print(f"check_pto_balance returned {balance['available_hours']} hours for E1001")

    print("MCP discovery and tool-call check passed")


if __name__ == "__main__":
    asyncio.run(main())
