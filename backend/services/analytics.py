"""Analytics and reporting (SRS sections 34, 38, 39)."""
from __future__ import annotations

from typing import Any

from ..database.relational import cursor, rows_to_dicts
from . import research


def all_projects() -> list[dict[str, Any]]:
    with cursor() as cur:
        rows = cur.execute("SELECT * FROM projects").fetchall()
    return rows_to_dicts(rows)


def all_users() -> list[dict[str, Any]]:
    with cursor() as cur:
        rows = cur.execute("SELECT * FROM users").fetchall()
    return [dict(r) for r in rows]


def researcher_summary(staff_id: str, projects: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    user = _find_user(staff_id)
    records = projects or [p for p in all_projects() if p.get("staff_id") == staff_id]
    verified = [p for p in records if p.get("verification_status") in ("verified", "frozen")]
    return {
        "staff_id": staff_id,
        "name": user.get("name") if user else staff_id,
        "department": user.get("department") if user else "",
        "designation": user.get("designation") if user else "",
        "total": len(records),
        "verified": len(verified),
        "score": round(sum(p.get("score", 0) for p in verified), 2),
        "by_type": research.aggregate_by(records, "type"),
        "by_category": research.aggregate_by(records, "category"),
    }


def department_report(department: str, projects: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    users = [u for u in all_users() if u.get("department") == department]
    staff_ids = {u.get("staff_id") for u in users}
    records = projects if projects is not None else all_projects()
    dept_records = [p for p in records if p.get("staff_id") in staff_ids]
    verified = [p for p in dept_records if p.get("verification_status") in ("verified", "frozen")]
    by_type = research.aggregate_by(verified, "type")
    return {
        "department": department,
        "faculty_count": len(users),
        "total": len(dept_records),
        "verified": len(verified),
        "publications": _count_types(verified, ("journal", "conference")),
        "projects": _count_types(verified, ("project",)),
        "patents": _count_types(verified, ("patent",)),
        "awards": _count_types(verified, ("award",)),
        "score": round(sum(p.get("score", 0) for p in verified), 2),
        "by_type": by_type,
    }


def institutional_report(projects: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    records = projects if projects is not None else all_projects()
    verified = [p for p in records if p.get("verification_status") in ("verified", "frozen")]
    departments = sorted({u.get("department") for u in all_users() if u.get("department")})
    return {
        "total_records": len(records),
        "verified": len(verified),
        "pending_review": sum(1 for p in records if p.get("verification_status") in ("submitted", "under_review")),
        "total_score": round(sum(p.get("score", 0) for p in verified), 2),
        "researchers": len({p.get("staff_id") for p in records}),
        "departments": departments,
        "department_reports": [department_report(d, records) for d in departments],
        "by_type": research.aggregate_by(verified, "type"),
        "by_year": research.aggregate_by(verified, "year"),
        "by_category": research.aggregate_by(verified, "category"),
    }


def analytics_overview() -> dict[str, Any]:
    records = all_projects()
    verified = [p for p in records if p.get("verification_status") in ("verified", "frozen")]
    return {
        "total_records": len(records),
        "verified": len(verified),
        "pending_review": sum(1 for p in records if p.get("verification_status") in ("submitted", "under_review")),
        "drafts": sum(1 for p in records if p.get("verification_status") == "draft"),
        "total_score": round(sum(p.get("score", 0) for p in verified), 2),
        "by_type": research.aggregate_by(verified, "type"),
        "by_year": research.aggregate_by(verified, "year"),
        "by_category": research.aggregate_by(verified, "category"),
        "top_researchers": _top_researchers(verified, 5),
        "recent": sorted(records, key=lambda p: p.get("created_at") or "", reverse=True)[:10],
    }


def _top_researchers(records: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    from collections import defaultdict

    agg: dict[str, float] = defaultdict(float)
    for p in records:
        agg[p.get("staff_id", "?")] += p.get("score", 0)
    ranked = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [{"staff_id": sid, "name": (_find_user(sid) or {}).get("name", sid), "score": round(s, 2)} for sid, s in ranked]


def _count_types(records: list[dict[str, Any]], types: tuple) -> int:
    return sum(1 for p in records if p.get("type") in types)


def _find_user(staff_id: str) -> dict[str, Any] | None:
    from ..services.authentication import get_user_by_staff_id

    return get_user_by_staff_id(staff_id)
