"""MCP server. Every agent data/policy operation is exposed as a typed MCP tool."""
from mcp.server.fastmcp import FastMCP

from . import data, rag

mcp = FastMCP("ClearHR Operations", instructions="Synthetic HR-policy tools. Never perform irreversible actions.")


@mcp.tool()
def search_policy_documents(query: str, limit: int = 4) -> list[dict]:
    """Retrieve grounded policy chunks with citation metadata."""
    return rag.search(query, min(max(limit, 1), 8))


@mcp.tool()
def get_policy_section(document: str, section: str) -> list[dict]:
    """Get a policy section by document filename/title and section name."""
    return [x for x in rag.load_index()["chunks"] if x["document"] == document and x["section"].lower() == section.lower()]


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
def create_mock_hr_ticket(employee_id: str, summary: str, category: str) -> dict:
    """Create a confirmation-required mock draft only; it never files a real ticket."""
    return data.create_ticket(employee_id, summary, category)


if __name__ == "__main__":
    mcp.run(transport="stdio")
