"""Bulk import + duplicate detection (SRS sections 35-36)."""
from __future__ import annotations

import csv
import io
import json
import re
from typing import Any
from xml.etree import ElementTree as ET

from . import research

# Searchable duplicate keys (SRS section 36).
DUPLICATE_KEYS = ("doi", "isbn", "patent_no", "title")


def detect_format(filename: str, content: bytes | str) -> str:
    if isinstance(content, str):
        content = content.encode("utf-8", errors="ignore")
    if filename.lower().endswith(".csv"):
        return "csv"
    if filename.lower().endswith(".json"):
        return "json"
    if filename.lower().endswith(".xml"):
        return "xml"
    if filename.lower().endswith((".xlsx", ".xls")):
        return "excel"
    head = content[:256].decode("utf-8", errors="ignore").strip().lower()
    if head.startswith("{"):
        return "json"
    if head.startswith("<"):
        return "xml"
    if "," in head:
        return "csv"
    return "json"


def parse(filename: str, content: bytes | str) -> list[dict[str, Any]]:
    fmt = detect_format(filename, content)
    if isinstance(content, str):
        content = content.encode("utf-8", errors="ignore")
    if fmt == "json":
        data = json.loads(content.decode("utf-8", errors="ignore"))
        return data if isinstance(data, list) else data.get("projects", data.get("records", []))
    if fmt == "csv":
        return list(csv.DictReader(io.StringIO(content.decode("utf-8", errors="ignore"))))
    if fmt == "excel":
        return _parse_excel(content)
    return _parse_xml(content)


def _parse_xml(content: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(content.decode("utf-8", errors="ignore"))
    items = root.findall(".//project") or root.findall(".//record") or [root]
    out: list[dict[str, Any]] = []
    for item in items:
        rec: dict[str, Any] = {}
        for child in item:
            tag = child.tag.split("}")[-1]
            text = (child.text or "").strip()
            if tag in ("details", "metadata", "authors"):
                try:
                    rec[tag] = json.loads(text) if text else {}
                except Exception:
                    rec[tag] = {}
            else:
                rec[tag] = text
        out.append(rec)
    return out


def _parse_excel(content: bytes) -> list[dict[str, Any]]:
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ValueError("openpyxl required for Excel import")
    wb = load_workbook(io.BytesIO(content), read_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = next(rows, None)
    if not header:
        return []
    keys = [str(h).strip() if h is not None else "" for h in header]
    out: list[dict[str, Any]] = []
    for row in rows:
        rec: dict[str, Any] = {}
        for k, v in zip(keys, row):
            if k and v is not None:
                rec[k] = v
        if rec:
            out.append(rec)
    return out


def normalize(record: dict[str, Any]) -> dict[str, Any]:
    """Map importer column names onto the canonical project shape."""
    pick = lambda *names: next((record.get(n) for n in names if record.get(n) not in (None, "")), None)
    details = dict(record.get("details", {}) or {})
    for key in ("journal", "impactFactor", "publisher", "amount", "scope", "bookType",
                "pedagogyType", "guidanceType", "subtype", "volume", "pages", "venue"):
        if record.get(key) is not None:
            details[key] = record[key]

    authors_raw = record.get("authors")
    authors: list[dict[str, Any]] = []
    if isinstance(authors_raw, list):
        authors = [a if isinstance(a, dict) else {"name": str(a)} for a in authors_raw]
    elif isinstance(authors_raw, str) and authors_raw:
        parts = [a.strip() for a in re.split(r"[;,]", authors_raw) if a.strip()]
        authors = [{"name": p} for p in parts]

    return {
        "title": pick("title", "Title", "paper_title") or "Untitled record",
        "staff_id": str(pick("staff_id", "staffId", "Staff ID", "author_id") or ""),
        "category": pick("category", "Category") or _category_from_type(pick("type", "Type", "activity_type")) ,
        "type": pick("type", "Type", "activity_type") or "journal",
        "status": pick("status", "Status") or "Active",
        "year": _to_int(pick("year", "Year", "publication_year")),
        "description": pick("description", "Description", "abstract") or "",
        "details": details,
        "authors": authors,
        "doi": pick("doi", "DOI") or "",
        "isbn": pick("isbn", "ISBN") or "",
        "patent_no": pick("patent_no", "patentNumber", "Patent Number") or "",
        "funding_agency": pick("funding_agency", "fundingAgency", "Funding Agency") or "",
        "verification_status": "draft",
        "source": "bulk_import",
    }


def _category_from_type(t: str | None) -> str:
    mapping = {
        "journal": "paper", "conference": "paper",
        "authored_book": "book", "chapter": "book", "edited_book": "book", "translation": "book",
        "course": "pedagogy", "mooc": "pedagogy", "econtent": "pedagogy",
        "phd_awarded": "guidance", "phd_submitted": "guidance", "dissertation": "guidance",
        "project": "project", "patent": "patent", "policy": "policy", "award": "award", "lecture": "lecture",
    }
    return mapping.get((t or "").lower(), "paper")


def _to_int(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None


def validate(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not record.get("title") or len(str(record["title"])) < 2:
        errors.append("title is required (min 2 characters)")
    year = record.get("year")
    if year is not None and (not isinstance(year, int) or year < 1900 or year > 2100):
        errors.append(f"year is invalid: {year}")
    return errors


def detect_duplicates(record: dict[str, Any], existing: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Find potential duplicates using title/DOI/ISBN/patent + year (SRS section 36)."""
    existing = existing if existing is not None else research.list_projects(limit=100000)
    title_norm = _normalize_title(record.get("title", ""))
    matches: list[dict[str, Any]] = []
    for candidate in existing:
        reasons: list[str] = []
        for key in ("doi", "isbn", "patent_no"):
            if record.get(key) and candidate.get(key) and str(record[key]).lower() == str(candidate[key]).lower():
                reasons.append(key)
        if title_norm and _normalize_title(candidate.get("title", "")) == title_norm:
            reasons.append("title")
        if reasons and record.get("year") and candidate.get("year") == record.get("year"):
            pass  # year strengthens confidence but is not required
        if reasons:
            matches.append({"id": candidate["id"], "title": candidate.get("title"), "reasons": reasons})
    return matches


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
