"""Research activities API (SRS sections 10-16, 28-29, 34, 37)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..schemas import CommentIn, ProjectIn, VerificationDecision, WorkloadEntry
from ..services import audit, research, verification
from ..services.authentication import can_edit_record, can
from .deps import get_current_user

router = APIRouter(prefix="/api/research", tags=["research"])


def _visible(records, user):
    """Role-scoped visibility: students/faculty see own data; admins see more."""
    role = user.get("role", "")
    if can(role, "rc_admin"):
        return records
    return [r for r in records if r.get("staff_id") == user.get("staff_id")]


@router.get("")
def list_research(
    staff_id: str | None = None,
    type_: str | None = Query(None, alias="type"),
    status: str | None = None,
    year: int | None = None,
    verification_status: str | None = None,
    search: str | None = None,
    user: dict = Depends(get_current_user),
):
    records = research.list_projects(
        staff_id=staff_id, type_=type_, status=status, year=year,
        verification=verification_status, search=search,
    )
    if not can(user.get("role", ""), "rc_admin") and not staff_id:
        records = [r for r in records if r.get("staff_id") == user.get("staff_id")]
    return research.enrich_projects(records)


@router.post("")
def create_research(body: ProjectIn, user: dict = Depends(get_current_user)):
    payload = body.model_dump()
    payload["staff_id"] = payload.get("staff_id") or user.get("staff_id")
    if payload.get("staff_id") != user.get("staff_id") and not can(user.get("role", ""), "college"):
        raise HTTPException(status_code=403, detail="Cannot create records for another user")
    payload["authors"] = [a.model_dump() for a in body.authors]
    project = research.create_project(payload, source="manual")
    audit.log(user.get("staff_id"), "project_create", "projects", project.get("id"))
    return research.enrich_projects([project])[0]


@router.get("/aggregate/{key}")
def aggregate(key: str, user: dict = Depends(get_current_user)):
    records = research.list_projects(limit=100000)
    records = _visible(records, user)
    return research.aggregate_by(records, key)


@router.get("/{project_id}")
def get_research(project_id: int, user: dict = Depends(get_current_user)):
    project = research.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Record not found")
    if project.get("staff_id") != user.get("staff_id") and not can(user.get("role", ""), "rc_admin"):
        raise HTTPException(status_code=403, detail="Not authorized to view this record")
    return research.enrich_projects([project])[0]


@router.put("/{project_id}")
def update_research(project_id: int, body: ProjectIn, user: dict = Depends(get_current_user)):
    project = research.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Record not found")
    if not can_edit_record(project, user):
        raise HTTPException(status_code=403, detail="Frozen records are locked to ordinary users")
    payload = body.model_dump()
    payload["authors"] = [a.model_dump() for a in body.authors]
    updated = research.update_project(project_id, payload)
    audit.log(user.get("staff_id"), "project_update", "projects", project_id)
    return research.enrich_projects([updated])[0]


@router.delete("/{project_id}")
def delete_research(project_id: int, user: dict = Depends(get_current_user)):
    project = research.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Record not found")
    if not can_edit_record(project, user):
        raise HTTPException(status_code=403, detail="Not authorized to delete this record")
    research.delete_project(project_id)
    audit.log(user.get("staff_id"), "project_delete", "projects", project_id)
    return {"success": True}


# ---------------------------------------------------------------- Verification
@router.post("/{project_id}/verify")
def verify(project_id: int, body: VerificationDecision, user: dict = Depends(get_current_user)):
    project = research.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Record not found")
    if body.action in ("approve", "reject", "freeze", "unfreeze", "request_changes") and not can(user.get("role", ""), "rc_admin"):
        raise HTTPException(status_code=403, detail="Research Administrator role required")
    try:
        updated = verification.apply_action(project_id, body.action, body.comment, user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    audit.log(user.get("staff_id"), f"verification_{body.action}", "projects", project_id, {"comment": body.comment})
    return research.enrich_projects([updated])[0]


# ---------------------------------------------------------------- Social
@router.post("/{project_id}/like")
def like(project_id: int, user: dict = Depends(get_current_user)):
    project = research.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Record not found")
    research.add_like(project_id, user.get("staff_id", ""))
    return research.enrich_projects([research.get_project(project_id)])[0]


@router.delete("/{project_id}/like")
def unlike(project_id: int, user: dict = Depends(get_current_user)):
    research.remove_like(project_id, user.get("staff_id", ""))
    return research.enrich_projects([research.get_project(project_id)])[0]


@router.post("/{project_id}/comments")
def comment(project_id: int, body: CommentIn, user: dict = Depends(get_current_user)):
    project = research.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Record not found")
    research.add_comment(project_id, user.get("staff_id", ""), body.text)
    return research.enrich_projects([research.get_project(project_id)])[0]


# ---------------------------------------------------------------- Workload
@router.get("/workload/{staff_id}")
def get_workload(staff_id: str, user: dict = Depends(get_current_user)):
    if staff_id != user.get("staff_id") and not can(user.get("role", ""), "rc_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    from ..database.relational import cursor

    with cursor() as cur:
        rows = cur.execute(
            "SELECT month, total_hours, teaching, research, administration FROM workload WHERE staff_id = ? ORDER BY month",
            (staff_id,),
        ).fetchall()
    return {"staff_id": staff_id, "months": [dict(r) for r in rows]}


@router.put("/workload/{staff_id}")
def upsert_workload(staff_id: str, body: WorkloadEntry, user: dict = Depends(get_current_user)):
    if staff_id != user.get("staff_id") and not can(user.get("role", ""), "rc_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    from ..database.relational import cursor

    with cursor() as cur:
        cur.execute(
            """INSERT INTO workload(staff_id, month, total_hours, teaching, research, administration)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(staff_id, month) DO UPDATE SET total_hours=excluded.total_hours,
               teaching=excluded.teaching, research=excluded.research, administration=excluded.administration""",
            (staff_id, body.month, body.total_hours, body.teaching, body.research, body.administration),
        )
    return {"success": True}
