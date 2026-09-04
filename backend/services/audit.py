"""Audit logging (SRS section 41)."""
from __future__ import annotations

import json
from typing import Any

from ..database.relational import cursor


def log(user_id: str, action: str, resource: str = "", resource_id: str = "", detail: Any = None) -> None:
    detail_text = json.dumps(detail, default=str)[:2000] if detail is not None else ""
    with cursor() as cur:
        cur.execute(
            "INSERT INTO audit_log(user_id, action, resource, resource_id, detail) VALUES(?,?,?,?,?)",
            (user_id or "", action, resource, str(resource_id), detail_text),
        )


def list_logs(limit: int = 200, user_id: str | None = None) -> list[dict[str, Any]]:
    with cursor() as cur:
        if user_id:
            rows = cur.execute(
                "SELECT * FROM audit_log WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
            ).fetchall()
        else:
            rows = cur.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
