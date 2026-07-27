from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .agent import respond
from .mcp_client import discover_tools
from .rag import build_index


@asynccontextmanager
async def lifespan(_: FastAPI):
    build_index()
    yield


app = FastAPI(title="ClearHR", version="0.1.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=3, max_length=3000)
    employee_id: str | None = Field(default=None, pattern=r"^E[0-9]{4}$")
    confirm_mock_action: bool = False


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
async def health() -> dict:
    try:
        tools = await discover_tools()
        return {"status": "ok", "mcp_connected": True, "mcp_tool_count": len(tools)}
    except Exception as exc:
        return {"status": "degraded", "mcp_connected": False, "detail": str(exc)}


@app.get("/tools")
async def tools() -> dict:
    return {"tools": await discover_tools()}


@app.post("/chat")
async def chat(request: ChatRequest) -> dict:
    try:
        return await respond(request.message, request.employee_id, request.confirm_mock_action)
    except Exception as exc:
        raise HTTPException(503, "The HR tool service is temporarily unavailable. Please retry.") from exc
