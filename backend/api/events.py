"""Research events API (SRS section 30)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import EventIn
from ..services import audit
from ..services.authentication import can
from ..database.relational import cursor
from .deps import get_current_user

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
def list_events(_: dict = Depends(get_current_user)):
    with cursor() as cur:
        rows = cur.execute("SELECT * FROM events ORDER BY date").fetchall()
    return [dict(r) for r in rows]


@router.post("")
def create_event(body: EventIn, user: dict = Depends(get_current_user)):
    if not can(user.get("role", ""), "rc_admin"):
        raise HTTPException(status_code=403, detail="Requires rc_admin role")
    with cursor() as cur:
        cur.execute(
            "INSERT INTO events(title, date, type, description, created_by) VALUES(?,?,?,?,?)",
            (body.title, body.date, body.type, body.description, user.get("staff_id", "")),
        )
        event_id = cur.lastrowid
    audit.log(user.get("staff_id"), "event_create", "events", event_id)
    return {"id": event_id, "success": True}


@router.put("/{event_id}")
def update_event(event_id: int, body: EventIn, user: dict = Depends(get_current_user)):
    if not can(user.get("role", ""), "rc_admin"):
        raise HTTPException(status_code=403, detail="Requires rc_admin role")
    with cursor() as cur:
        cur.execute(
            "UPDATE events SET title=?, date=?, type=?, description=? WHERE id=?",
            (body.title, body.date, body.type, body.description, event_id),
        )
    audit.log(user.get("staff_id"), "event_update", "events", event_id)
    return {"success": True}


@router.delete("/{event_id}")
def delete_event(event_id: int, user: dict = Depends(get_current_user)):
    if not can(user.get("role", ""), "college"):
        raise HTTPException(status_code=403, detail="Requires college role")
    with cursor() as cur:
        cur.execute("DELETE FROM events WHERE id=?", (event_id,))
    audit.log(user.get("staff_id"), "event_delete", "events", event_id)
    return {"success": True}
