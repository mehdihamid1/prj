"""MCP client adapter used by the orchestrator.

For free-tier single-service deployment the adapter dispatches through FastMCP's
registered tool manager in-process. This is still the MCP tool boundary: the
agent discovers tool schemas and invokes names/arguments through FastMCP, rather
than importing or calling the data functions. `app.mcp_server` can also be run
as a separate stdio MCP process with `python -m app.mcp_server`.
"""
from __future__ import annotations

import json
from typing import Any

from .mcp_server import mcp


async def discover_tools() -> list[dict[str, Any]]:
    tools = await mcp.list_tools()
    return [{"name": tool.name, "description": tool.description, "inputSchema": tool.inputSchema} for tool in tools]


async def call(name: str, arguments: dict[str, Any]) -> Any:
    content = await mcp.call_tool(name, arguments)
    # MCP SDK v1.12 returns (content_blocks, structured_result) for tools with
    # an output schema; prefer the structured value when it is available.
    if isinstance(content, tuple):
        blocks, structured = content
        if isinstance(structured, dict):
            return structured.get("result", structured)
        content = blocks
    if isinstance(content, dict):
        return content
    text = "".join(item.text for item in content if hasattr(item, "text"))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
