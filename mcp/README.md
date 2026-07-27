# MCP Server

The executable FastMCP server and all six tool definitions are in `../app/mcp_server.py`. Run it with:

```bash
python -m app.mcp_server
```

The application invokes those registered tools through `app/mcp_client.py`; see `design-and-evaluation.md` for schemas and architecture.
