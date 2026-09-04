"""Research activity CRUD, search and aggregation (SRS sections 10-16, 34, 37)."""
from __future__ import annotations

import json
from typing import Any

from ..database.relational import cursor, now_iso, row_to_dict, rows_to_dicts
from ..services import scoring


def _payload(project: dict[str, Any]) -> tuple:
    return (
        project.get("staff_id", ""),
        project.get("category", "paper"),
        project.get("type", "journal"),
        project.get("title", ""),
        project.get("status", "Active"),
        project.get("year"),
        project.get("description", ""),
        json.dumps(project.get("details", {}), default=str),
        json.dumps(project.get("authors", []), default=str),
        json.dumps(project.get("metadata", {}), default=str),
        project.get("doi", ""),
        project.get("isbn", ""),
        project.get("patent_no", ""),
        project.get("funding_agency", ""),
    )


def create_project(project: dict[str, Any], source: str = "manual", verification: str = "draft") -> dict[str, Any]:
    score, breakdown = scoring.score_project(project)
    with cursor() as cur:
        cur.execute(
            """INSERT INTO projects(staff_id, category, type, title, status, year, description,
               details, authors, metadata, verification_status, score, score_breakdown,
               doi, isbn, patent_no, funding_agency, source)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (*_payload(project), verification, score, json.dumps(breakdown, default=str), source),
        )
        project_id = cur.lastrowid
    return get_project(project_id) or {}


def get_project(project_id: int) -> dict[str, Any] | None:
    with cursor() as cur:
        row = cur.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return row_to_dict(row)


def list_projects(
    staff_id: str | None = None,
    type_: str | None = None,
    status: str | None = None,
    year: int | None = None,
    verification: str | None = None,
    department: str | None = None,
    search: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM projects WHERE 1=1"
    params: list[Any] = []
    if staff_id:
        query += " AND staff_id = ?"
        params.append(staff_id)
    if type_:
        query += " AND type = ?"
        params.append(type_)
    if status:
        query += " AND status = ?"
        params.append(status)
    if year is not None:
        query += " AND year = ?"
        params.append(year)
    if verification:
        query += " AND verification_status = ?"
        params.append(verification)
    if search:
        query += """ AND (title LIKE ? OR doi LIKE ? OR patent_no LIKE ? OR funding_agency LIKE ?
                        OR description LIKE ?)"""
        like = f"%{search}%"
        params.extend([like, like, like, like, like])
    query += " ORDER BY year DESC, id DESC LIMIT ?"
    params.append(limit)
    with cursor() as cur:
        rows = cur.execute(query, params).fetchall()
    return rows_to_dicts(rows)


def update_project(project_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    existing = get_project(project_id)
    if not existing:
        return None
    merged = {**existing, **{k: v for k, v in data.items() if k != "authors"}}
    if "authors" in data:
        merged["authors"] = data["authors"]
    merged["details"] = {**existing.get("details", {}), **data.get("details", {})}
    merged["metadata"] = {**existing.get("metadata", {}), **data.get("metadata", {})}
    score, breakdown = scoring.score_project(merged)
    with cursor() as cur:
        cur.execute(
            """UPDATE projects SET category=?, type=?, title=?, status=?, year=?, description=?,
               details=?, authors=?, metadata=?, doi=?, isbn=?, patent_no=?, funding_agency=?,
               score=?, score_breakdown=?, updated_at=? WHERE id=?""",
            (
                merged["category"], merged["type"], merged["title"], merged.get("status", "Active"),
                merged.get("year"), merged.get("description", ""),
                json.dumps(merged["details"], default=str), json.dumps(merged["authors"], default=str),
                json.dumps(merged["metadata"], default=str),
                merged.get("doi", ""), merged.get("isbn", ""), merged.get("patent_no", ""),
                merged.get("funding_agency", ""), score, json.dumps(breakdown, default=str),
                now_iso(), project_id,
            ),
        )
    return get_project(project_id)


def set_verification(project_id: int, status: str) -> dict[str, Any] | None:
    with cursor() as cur:
        cur.execute(
            "UPDATE projects SET verification_status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), project_id),
        )
    return get_project(project_id)


def delete_project(project_id: int) -> bool:
    with cursor() as cur:
        cur.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return cur.rowcount > 0


def add_like(project_id: int, user_id: str) -> dict[str, Any]:
    with cursor() as cur:
        cur.execute("DELETE FROM social WHERE project_id = ? AND user_id = ? AND kind = 'like'", (project_id, user_id))
        cur.execute("INSERT INTO social(project_id, user_id, kind) VALUES(?,?, 'like')", (project_id, user_id))
    return get_project(project_id) or {}


def remove_like(project_id: int, user_id: str) -> dict[str, Any]:
    with cursor() as cur:
        cur.execute("DELETE FROM social WHERE project_id = ? AND user_id = ? AND kind = 'like'", (project_id, user_id))
    return get_project(project_id) or {}


def add_comment(project_id: int, user_id: str, text: str) -> dict[str, Any]:
    with cursor() as cur:
        cur.execute(
            "INSERT INTO social(project_id, user_id, kind, text) VALUES(?,?, 'comment', ?)",
            (project_id, user_id, text),
        )
    return get_project(project_id) or {}


def _enrich(project: dict[str, Any]) -> dict[str, Any]:
    with cursor() as cur:
        likes = cur.execute(
            "SELECT COUNT(*) AS n FROM social WHERE project_id = ? AND kind = 'like'", (project["id"],)
        ).fetchone()
        comments = cur.execute(
            "SELECT user_id, text, created_at FROM social WHERE project_id = ? AND kind = 'comment' ORDER BY id",
            (project["id"],),
        ).fetchall()
    project["likes"] = likes["n"] if likes else 0
    project["comments"] = [dict(c) for c in comments]
    return project


def enrich_projects(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_enrich(p) for p in projects]


def aggregate_by(projects: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Aggregate research data by a field (SRS section 34)."""
    groups: dict[str, dict[str, Any]] = {}
    for p in projects:
        value = p.get(key, "Unknown") or "Unknown"
        g = groups.setdefault(value, {"key": value, "count": 0, "score": 0.0, "types": {}})
        g["count"] += 1
        g["score"] += p.get("score", 0)
        t = p.get("type", "other")
        g["types"][t] = g["types"].get(t, 0) + 1
    return sorted(groups.values(), key=lambda g: g["score"], reverse=True)
