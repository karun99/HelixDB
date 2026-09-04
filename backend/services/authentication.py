"""Authentication: password hashing, JWT tokens, role-based access control.

SRS sections 5-9: four user levels (student, faculty, rc_admin, college),
mock credentials in development only.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from ..config.settings import settings
from ..database.relational import cursor, row_to_dict

ROLE_RANK = {"student": 1, "faculty": 2, "rc_admin": 3, "college": 4}
ROLE_LABELS = {
    "student": "Student",
    "faculty": "Faculty",
    "rc_admin": "Research Administrator",
    "college": "College Administrator",
    "dept_hod": "Department HOD",
    "admin": "System Admin",
}


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return salt, digest


def verify_password(password: str, salt: str, digest: str) -> bool:
    _, candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, digest)


def create_user(
    staff_id: str,
    name: str,
    role: str = "faculty",
    designation: str = "",
    department: str = "",
    specialisation: str = "",
    email: str = "",
    password: str = "helixdb",
) -> dict[str, Any]:
    salt, digest = hash_password(password)
    with cursor() as cur:
        cur.execute(
            """INSERT INTO users(staff_id, name, role, designation, department,
               specialisation, email, password_hash) VALUES(?,?,?,?,?,?,?,?)""",
            (staff_id, name, role, designation, department, specialisation, email, f"{salt}:{digest}"),
        )
    return get_user_by_staff_id(staff_id) or {}


def get_user_by_staff_id(staff_id: str) -> dict[str, Any] | None:
    with cursor() as cur:
        row = cur.execute("SELECT * FROM users WHERE staff_id = ?", (staff_id,)).fetchone()
    return row_to_dict(row)


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with cursor() as cur:
        row = cur.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return row_to_dict(row)


def list_users() -> list[dict[str, Any]]:
    with cursor() as cur:
        rows = cur.execute("SELECT * FROM users ORDER BY name").fetchall()
    return row_to_dict.__self__ and [_strip(u) for u in [row_to_dict(r) for r in rows] if u]


def _strip(user: dict[str, Any]) -> dict[str, Any]:
    user.pop("password_hash", None)
    return user


def authenticate(staff_id: str, password: str) -> dict[str, Any] | None:
    user = get_user_by_staff_id(staff_id)
    if not user:
        return None
    salt, digest = (user.get("password_hash") or "").split(":", 1)
    if not verify_password(password, salt, digest):
        return None
    return _strip(user)


def create_access_token(user: dict[str, Any]) -> str:
    payload = {
        "sub": user["staff_id"],
        "role": user.get("role", "faculty"),
        "name": user.get("name", ""),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.PyJWTError:
        return None


def user_from_token(token: str) -> dict[str, Any] | None:
    payload = decode_token(token)
    if not payload:
        return None
    return get_user_by_staff_id(payload.get("sub", ""))


def can(role: str, minimum_role: str) -> bool:
    return ROLE_RANK.get(role, 0) >= ROLE_RANK.get(minimum_role, 0)


def is_owner(record_staff_id: str, user: dict[str, Any]) -> bool:
    return record_staff_id == user.get("staff_id")


def can_edit_record(record: dict[str, Any], user: dict[str, Any]) -> bool:
    """Frozen records are locked for ordinary users (SRS section 29)."""
    role = user.get("role", "")
    if record.get("verification_status") == "frozen":
        return role in ("college", "admin")
    if role in ("college", "admin"):
        return True
    return is_owner(record.get("staff_id", ""), user)
