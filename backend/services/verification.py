"""Research verification workflow (SRS sections 28-29).

States: draft -> submitted -> under_review -> verified -> rejected | frozen.
Frozen records are locked to ordinary users; college admin has controlled
override (SRS section 29).
"""
from __future__ import annotations

from typing import Any

from ..database.relational import now_iso, row_to_dict, cursor

VALID_STATES = {"draft", "submitted", "under_review", "verified", "rejected", "frozen"}

TRANSITIONS = {
    "draft": {"submit"},
    "submitted": {"approve", "reject", "request_changes"},
    "under_review": {"approve", "reject", "request_changes"},
    "verified": {"freeze", "reject"},
    "rejected": {"resubmit", "approve"},
    "frozen": {"unfreeze", "override_edit"},
}

ACTION_TO_STATE = {
    "submit": "submitted",
    "approve": "verified",
    "reject": "rejected",
    "request_changes": "under_review",
    "freeze": "frozen",
    "unfreeze": "verified",
    "resubmit": "submitted",
    "override_edit": "under_review",
}


def allowed_actions(user: dict[str, Any], record: dict[str, Any]) -> list[str]:
    role = user.get("role", "")
    current = record.get("verification_status", "draft")
    actions = list(TRANSITIONS.get(current, []))
    if role in ("rc_admin", "college", "admin") and current in ("submitted", "under_review"):
        actions += ["approve", "reject", "request_changes"]
    if role in ("rc_admin", "college", "admin") and current == "verified":
        actions.append("freeze")
    if role == "college" and current == "frozen":
        actions += ["unfreeze", "override_edit"]
    return sorted(set(actions))


def apply_action(record_id: int, action: str, comment: str = "", actor: dict[str, Any] | None = None) -> dict[str, Any] | None:
    record = get_record(record_id)
    if not record:
        return None
    current = record.get("verification_status", "draft")
    allowed = allowed_actions(actor or {}, record)
    if action not in allowed:
        raise PermissionError(f"Action '{action}' not allowed for current state '{current}'")
    new_state = ACTION_TO_STATE.get(action)
    if not new_state:
        raise ValueError(f"Unknown action: {action}")
    with cursor() as cur:
        cur.execute(
            "UPDATE projects SET verification_status = ?, updated_at = ? WHERE id = ?",
            (new_state, now_iso(), record_id),
        )
        if comment:
            cur.execute(
                "INSERT INTO social(project_id, user_id, kind, text) VALUES(?,?, 'review', ?)",
                (record_id, (actor or {}).get("staff_id", ""), comment),
            )
    return get_record(record_id)


def get_record(record_id: int) -> dict[str, Any] | None:
    from ..services.research import get_project

    return get_project(record_id)
