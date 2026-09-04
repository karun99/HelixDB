"""FastAPI dependencies: auth + role-based access control (SRS section 6)."""
from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..services.authentication import ROLE_RANK, user_from_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, Any]:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = user_from_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


def require_role(minimum_role: str):
    def checker(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if ROLE_RANK.get(user.get("role", ""), 0) < ROLE_RANK.get(minimum_role, 99):
            raise HTTPException(status_code=403, detail=f"Requires role >= {minimum_role}")
        return user

    return checker
