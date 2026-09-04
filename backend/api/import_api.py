"""Bulk import + duplicate detection API (SRS sections 35-36)."""
from __future__ import annotations

import io
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from ..schemas import ProjectIn
from ..services import audit, importer, research
from ..services.authentication import can
from .deps import get_current_user

router = APIRouter(prefix="/api/import", tags=["import"])


async def _read(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 20MB)")
    return data


@router.post("/preview")
async def preview(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    content = await _read(file)
    try:
        raw = importer.parse(file.filename or "upload.json", content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}")
    normalized = [importer.normalize(r) for r in raw]
    existing = research.list_projects(limit=100000)
    rows: list[dict[str, Any]] = []
    for rec in normalized:
        errors = importer.validate(rec)
        duplicates = importer.detect_duplicates(rec, existing)
        rows.append({"record": rec, "errors": errors, "duplicates": duplicates})
    return {"total": len(rows), "rows": rows}


@router.post("")
async def import_records(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    content = await _read(file)
    try:
        raw = importer.parse(file.filename or "upload.json", content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}")

    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    existing = research.list_projects(limit=100000)
    for rec in raw:
        normalized = importer.normalize(rec)
        normalized["staff_id"] = normalized.get("staff_id") or user.get("staff_id", "")
        errors = importer.validate(normalized)
        if errors:
            skipped.append({"title": normalized.get("title"), "errors": errors})
            continue
        # Bulk import never auto-verifies (SRS section 35).
        project = research.create_project(normalized, source="bulk_import", verification="draft")
        created.append({"id": project.get("id"), "title": normalized.get("title")})
    audit.log(user.get("staff_id"), "bulk_import", "projects", None, {"created": len(created), "skipped": len(skipped)})
    return {"created": len(created), "skipped": len(skipped), "records": created, "skipped_details": skipped}


@router.post("/check-duplicates")
async def check_duplicates(body: dict[str, Any], user: dict = Depends(get_current_user)):
    record = importer.normalize(body.get("record", body))
    existing = research.list_projects(limit=100000)
    return {"duplicates": importer.detect_duplicates(record, existing)}
