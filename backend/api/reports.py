"""Reports + analytics API (SRS sections 34, 38-39)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..services import analytics
from ..services.authentication import can
from .deps import get_current_user

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/reports/institutional")
def institutional(user: dict = Depends(get_current_user)):
    return analytics.institutional_report()


@router.get("/reports/department/{department}")
def department(department: str, user: dict = Depends(get_current_user)):
    if not can(user.get("role", ""), "rc_admin"):
        department = user.get("department", department)
    return analytics.department_report(department)


@router.get("/reports/researcher/{staff_id}")
def researcher(staff_id: str, user: dict = Depends(get_current_user)):
    if not can(user.get("role", ""), "rc_admin") and staff_id != user.get("staff_id"):
        staff_id = user.get("staff_id")
    return analytics.researcher_summary(staff_id)


@router.get("/analytics/overview")
def overview(user: dict = Depends(get_current_user)):
    return analytics.analytics_overview()


@router.get("/analytics/topics")
def topics(user: dict = Depends(get_current_user)):
    """Topic clustering placeholder — operates on stored data only (SRS section 39)."""
    records = analytics.all_projects()
    from collections import Counter

    words: Counter[str] = Counter()
    for p in records:
        title = p.get("title", "")
        for w in title.lower().replace(":", " ").split():
            if len(w) > 3 and w not in {"with", "from", "this", "that", "their", "using", "based", "data", "research", "study"}:
                words[w] += 1
    return {"topics": [{"word": w, "count": c} for w, c in words.most_common(30)]}
