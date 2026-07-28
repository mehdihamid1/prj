"""MCP server. Every agent data/policy operation is exposed as a typed MCP tool."""
from mcp.server.fastmcp import FastMCP

from . import data, rag

mcp = FastMCP(
    "ClearHR Operations",
    instructions="Synthetic HR-policy tools. Never perform irreversible actions.",
    log_level="WARNING",
)


@mcp.tool()
def search_policy_documents(query: str, limit: int = 4) -> list[dict]:
    """Retrieve grounded policy chunks with citation metadata."""
    return rag.search(query, min(max(limit, 1), 8))


@mcp.tool()
def get_policy_section(document: str, section: str) -> list[dict]:
    """Get a policy section by document filename/title and section name."""
    # The persisted index includes an internal embedding used only by retrieval.
    # Do not send it over MCP: it inflates model context and is not citation data.
    matches = [
        {key: value for key, value in item.items() if key != "embedding"}
        for item in rag.load_index()["chunks"]
        if item["document"] == document and item["section"].lower() == section.lower()
    ]
    return matches[:8]


@mcp.tool()
def lookup_employee_profile(employee_id: str) -> dict:
    """Look up a synthetic employee profile."""
    return data.employee(employee_id) or {"error": "Employee not found", "employee_id": employee_id}


@mcp.tool()
def check_pto_balance(employee_id: str) -> dict:
    """Return a synthetic PTO balance."""
    return data.pto_balance(employee_id) or {"error": "PTO record not found", "employee_id": employee_id}


@mcp.tool()
def lookup_benefits_status(employee_id: str) -> dict:
    """Return synthetic benefits enrollment information."""
    return data.benefits(employee_id) or {"error": "Benefits record not found", "employee_id": employee_id}


@mcp.tool()
def create_mock_hr_ticket(
    employee_id: str, summary: str, category: str, confirmed: bool = False
) -> dict:
    """Create a confirmed mock draft only; it never files a real ticket."""
    # Enforce this at the tool boundary as well as in the agent. That protects
    # callers using a future agent implementation or direct MCP client.
    if not confirmed:
        return {
            "error": "confirmation_required",
            "detail": "Set confirmed=true only after the user explicitly confirms the mock draft.",
        }
    if not data.employee(employee_id):
        return {"error": "Employee not found", "employee_id": employee_id}
    return data.create_ticket(employee_id, summary, category)


if __name__ == "__main__":
    mcp.run(transport="stdio")
