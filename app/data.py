from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .settings import DATA_DIR


def _read(name: str) -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / name).read_text())


def employee(employee_id: str) -> dict[str, Any] | None:
    return next((row for row in _read("employees.json") if row["employee_id"] == employee_id), None)


def pto_balance(employee_id: str) -> dict[str, Any] | None:
    return next((row for row in _read("pto_balances.json") if row["employee_id"] == employee_id), None)


def benefits(employee_id: str) -> dict[str, Any] | None:
    return next((row for row in _read("benefits.json") if row["employee_id"] == employee_id), None)


def create_ticket(employee_id: str, summary: str, category: str) -> dict[str, Any]:
    # Deliberately a mock action: no external system is modified.
    return {"ticket_id": f"MOCK-{datetime.now(timezone.utc):%Y%m%d%H%M%S}", "employee_id": employee_id,
            "category": category, "summary": summary, "status": "draft", "requires_confirmation": True}
