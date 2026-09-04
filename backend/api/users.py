"""Users API (SRS sections 5-6, 9)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import UserCreate, UserOut, UserUpdate
from ..services import audit
from ..services.authentication import ROLE_LABELS, create_user, get_user_by_staff_id, list_users
from .deps import get_current_user, require_role

router = APIRouter(prefix="/api/users", tags=["users"])


def _out(user: dict) -> dict:
    user["role_label"] = ROLE_LABELS.get(user.get("role", ""), user.get("role", ""))
    return user


@router.get("")
def get_users(_: dict = Depends(get_current_user)):
    return [_out(u) for u in list_users()]


@router.post("", response_model=UserOut)
def add_user(body: UserCreate, admin: dict = Depends(require_role("college"))):
    if get_user_by_staff_id(body.staff_id):
        raise HTTPException(status_code=409, detail=f"staff_id {body.staff_id} already exists")
    user = create_user(
        body.staff_id, body.name, body.role, body.designation, body.department,
        body.specialisation, body.email, body.password,
    )
    audit.log(admin.get("staff_id"), "user_create", "users", body.staff_id)
    return _out(user)


@router.put("/{staff_id}", response_model=UserOut)
def update_user(staff_id: str, body: UserUpdate, admin: dict = Depends(require_role("college"))):
    user = get_user_by_staff_id(staff_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    from ..database.relational import cursor, now_iso

    fields = body.model_dump(exclude_none=True)
    if fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        params = [*fields.values(), now_iso(), user["id"]]
        with cursor() as cur:
            cur.execute(f"UPDATE users SET {sets}, updated_at = ? WHERE id = ?", params)
    audit.log(admin.get("staff_id"), "user_update", "users", staff_id)
    return _out(get_user_by_staff_id(staff_id) or {})


@router.delete("/{staff_id}")
def delete_user(staff_id: str, admin: dict = Depends(require_role("college"))):
    if staff_id == admin.get("staff_id"):
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    from ..database.relational import cursor

    with cursor() as cur:
        cur.execute("DELETE FROM users WHERE staff_id = ?", (staff_id,))
    audit.log(admin.get("staff_id"), "user_delete", "users", staff_id)
    return {"success": True}
