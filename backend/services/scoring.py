"""Configurable research scoring engine (SRS sections 17-27).

The scoring framework is stored in the meta table as institutional
configuration rather than hardcoded. Base score + optional age decay, with
per-category tiers and principal/co-author contribution allocation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ..database.relational import get_meta


def get_config() -> dict[str, Any]:
    return get_meta("scoring_config") or {}


def _tier(category_cfg: dict[str, Any], details: dict[str, Any], project_type: str) -> dict[str, Any] | None:
    """Select a tier for a category based on details + type."""
    tiers = category_cfg.get("tiers", [])
    if not tiers:
        return None
    if len(tiers) == 1:
        return tiers[0]
    if project_type == "journal":
        impact = _as_float(details.get("impactFactor", details.get("impact_factor", details.get("if"))))
        refereed = details.get("refereed", True)
        if not refereed:
            return _find(tiers, "ugc") or tiers[0]
        if impact is None:
            return _find(tiers, "refereed_no_if") or tiers[0]
        return _by_if(tiers, impact)
    if project_type == "book":
        key = details.get("bookType", details.get("subtype", "chapter"))
        return _find(tiers, key) or tiers[0]
    if project_type == "pedagogy":
        key = details.get("pedagogyType", details.get("subtype", "course"))
        return _find(tiers, key) or tiers[0]
    if project_type == "guidance":
        key = details.get("guidanceType", details.get("subtype", "dissertation"))
        return _find(tiers, key) or tiers[0]
    if project_type == "project":
        completed = str(details.get("status", details.get("completionStatus", "Ongoing"))).lower() in ("completed", "complete", "closed")
        amount = _as_float(details.get("amount", details.get("sanctionAmount", details.get("projectValue"))))
        threshold = _as_float(category_cfg.get("amount_threshold")) or 1_000_000
        high = amount is not None and amount >= threshold
        key = f"{'completed' if completed else 'ongoing'}_{'high' if high else 'low'}"
        return _find(tiers, key) or tiers[0]
    scope = str(details.get("scope", details.get("level", details.get("subtype", "")))).lower()
    if "state" in scope or scope in ("state", "state_university", "state/university", "university"):
        return _find(tiers, "state") or _find(tiers, "state_university") or tiers[-1]
    if "international" in scope or scope == "intl" or scope == "abroad" or scope in ("international", "intl_abroad", "intl_within"):
        return _find(tiers, "international") or _find(tiers, "intl_abroad") or _find(tiers, "intl_within") or tiers[0]
    if "national" in scope or scope == "national":
        return _find(tiers, "national") or tiers[0]
    if project_type == "lecture":
        scope = str(details.get("scope", details.get("level", ""))).lower()
        if "abroad" in scope:
            return _find(tiers, "intl_abroad") or tiers[0]
        if "within" in scope or "within-country" in scope:
            return _find(tiers, "intl_within") or tiers[0]
        if "national" in scope:
            return _find(tiers, "national") or tiers[1]
        return _find(tiers, "state_university") or tiers[-1]
    return tiers[0]


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _find(tiers: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    for t in tiers:
        if t.get("key") == key:
            return t
    return None


def _by_if(tiers: list[dict[str, Any]], impact: float) -> dict[str, Any] | None:
    candidates = [t for t in tiers if _in_range(t, impact)]
    if not candidates:
        return tiers[-1] if impact > 10 else tiers[0]
    return candidates[0]


def _in_range(tier: dict[str, Any], value: float) -> bool:
    lo = _as_float(tier.get("min"))
    hi = _as_float(tier.get("max"))
    if lo is not None and value < lo:
        return False
    if hi is not None and value >= hi:
        return False
    return True


def compute_score(project: dict[str, Any], current_year: int | None = None) -> dict[str, Any]:
    """Compute { score, base, adjusted, tier, age, contributions }."""
    cfg = get_config()
    now = current_year or datetime.now().year
    ptype = project.get("type", "journal")
    details = project.get("details") or {}
    cat_cfg = cfg.get("categories", {}).get(ptype) or cfg.get("categories", {}).get(project.get("category"), {})

    if not cat_cfg:
        base = float(cfg.get("baseScoreModel", {}).get(ptype, 0))
        tier = {"key": ptype, "label": ptype, "base": base}
    else:
        tier = _tier(cat_cfg, details, ptype) or {"key": "default", "label": ptype, "base": cat_cfg.get("default", 0)}

    base = float(tier.get("base", 0))
    year = project.get("year")
    age = max(0, now - year) if isinstance(year, int) else 0
    decay = cfg.get("ageDecay", {})
    adjusted = base
    if decay.get("enabled") and age > 0:
        adjusted = base - age * float(decay.get("factor", 0.5))

    # Contribution allocation (SRS section 27).
    authors = project.get("authors") or []
    principal_share = float(cfg.get("principalShare", 0.7))
    principal = 0.0
    co_total = 0.0
    if authors:
        principal = adjusted * principal_share
        co_count = max(1, len(authors) - 1)
        co_total = (adjusted * (1 - principal_share)) / co_count
    else:
        principal = adjusted

    owner_share = principal
    if authors:
        owner = project.get("staff_id", "")
        for a in authors:
            if isinstance(a, dict) and a.get("staff_id") == owner:
                owner_share = principal if a.get("role", "principal_author") in ("principal_author", "principal_investigator", "supervisor", "editor") else co_total
                break

    return {
        "score": round(adjusted, 2),
        "base": round(base, 2),
        "adjusted": round(adjusted, 2),
        "age": age,
        "tier": tier.get("key", "default"),
        "tier_label": tier.get("label", ""),
        "principal_share": round(principal, 2),
        "co_author_share": round(co_total, 2),
        "owner_share": round(owner_share, 2),
        "decay_factor": decay.get("factor") if decay.get("enabled") else 0,
    }


def score_project(project: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    breakdown = compute_score(project)
    return float(breakdown["score"]), breakdown
