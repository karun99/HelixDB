"""Authentication API (SRS sections 7-8)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..schemas import LoginRequest, TokenOut, UserUpdate
from ..services import audit
from ..services.authentication import (
    ROLE_LABELS,
    authenticate,
    create_access_token,
    get_user_by_staff_id,
)
from .deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginRequest):
    user = authenticate(body.staff_id, body.password)
    if not user:
        audit.log(body.staff_id, "login_failed", "auth")
        raise HTTPException(status_code=401, detail="Invalid staff ID or password")
    user["role_label"] = ROLE_LABELS.get(user.get("role", ""), user.get("role", ""))
    token = create_access_token(user)
    audit.log(user["staff_id"], "login", "auth")
    return TokenOut(access_token=token, user=user)


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.put("/me")
def update_me(body: UserUpdate, user: dict = Depends(get_current_user)):
    from ..database.relational import cursor, now_iso

    fields = body.model_dump(exclude_none=True)
    if fields:
        sets = ", ".join(f"{k} = ?" for k in fields)
        params = [*fields.values(), now_iso(), user["id"]]
        with cursor() as cur:
            cur.execute(f"UPDATE users SET {sets}, updated_at = ? WHERE id = ?", params)
    return get_user_by_staff_id(user["staff_id"])
