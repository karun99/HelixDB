"""Settings + audit API (SRS sections 17-18, 31-32, 41).

Institutional configuration is stored in the `meta` table so it can be edited
at runtime from the admin UI.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..database.relational import get_meta, set_meta
from ..schemas import BackupConfig, CollegeConfig, DatabaseConfig
from ..services import audit
from ..services.authentication import can
from .deps import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings(user: dict = Depends(get_current_user)):
    return {
        "college_config": get_meta("college_config", {}),
        "database_config": get_meta("database_config", {}),
        "backup_config": get_meta("backup_config", {}),
    }


@router.put("/college")
def update_college(body: CollegeConfig, user: dict = Depends(get_current_user)):
    if not can(user.get("role", ""), "college"):
        raise HTTPException(status_code=403, detail="Requires college role")
    set_meta("college_config", body.model_dump())
    audit.log(user.get("staff_id"), "settings_college_update", "meta", "college_config")
    return get_meta("college_config")


@router.put("/database")
def update_database(body: DatabaseConfig, user: dict = Depends(get_current_user)):
    if not can(user.get("role", ""), "college"):
        raise HTTPException(status_code=403, detail="Requires college role")
    set_meta("database_config", body.model_dump())
    audit.log(user.get("staff_id"), "settings_database_update", "meta", "database_config")
    return get_meta("database_config")


@router.put("/backup")
def update_backup(body: BackupConfig, user: dict = Depends(get_current_user)):
    if not can(user.get("role", ""), "college"):
        raise HTTPException(status_code=403, detail="Requires college role")
    set_meta("backup_config", body.model_dump())
    audit.log(user.get("staff_id"), "settings_backup_update", "meta", "backup_config")
    return get_meta("backup_config")


@router.get("/scoring")
def get_scoring(user: dict = Depends(get_current_user)):
    return get_meta("scoring_config", {})


@router.put("/scoring")
def update_scoring(body: dict[str, Any], user: dict = Depends(get_current_user)):
    if not can(user.get("role", ""), "college"):
        raise HTTPException(status_code=403, detail="Requires college role")
    set_meta("scoring_config", body)
    audit.log(user.get("staff_id"), "settings_scoring_update", "meta", "scoring_config")
    return get_meta("scoring_config")


@router.get("/audit")
def get_audit(limit: int = 200, user: dict = Depends(get_current_user)):
    if not can(user.get("role", ""), "rc_admin"):
        raise HTTPException(status_code=403, detail="Requires rc_admin role")
    return audit.list_logs(limit=limit)
