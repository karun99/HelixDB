"""OCR-assisted data entry API (SRS section 40)."""
from __future__ import annotations

import io

from fastapi import APIRouter, Depends, UploadFile, File

from ..schemas import ProjectIn
from ..services import audit, importer, ocr, research
from ..services.authentication import can
from .deps import get_current_user

router = APIRouter(prefix="/api/ocr", tags=["ocr"])


@router.post("/extract")
async def extract(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        content = content[:20 * 1024 * 1024]
    try:
        fields = ocr.ocr_from_file(file.filename or "document.pdf", content)
    except Exception as exc:
        fields = {"_error": str(exc), "_engine": "failed"}
    return fields


@router.post("/create")
async def create_from_ocr(body: ProjectIn, user: dict = Depends(get_current_user)):
    """Create an UNVERIFIED record from OCR-extracted metadata (SRS section 40)."""
    payload = body.model_dump()
    payload["staff_id"] = payload.get("staff_id") or user.get("staff_id", "")
    payload["authors"] = [a.model_dump() for a in body.authors]
    if payload.get("metadata", {}).get("_unverified"):
        payload["verification_status"] = "draft"
    project = research.create_project(payload, source="ocr", verification="draft")
    audit.log(user.get("staff_id"), "ocr_create", "projects", project.get("id"))
    return research.enrich_projects([project])[0]
