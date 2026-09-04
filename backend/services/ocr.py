"""OCR-assisted research data entry (SRS section 40).

Extracted metadata is treated as UNVERIFIED until reviewed. The service tries
tesseract when available; otherwise it falls back to filename/text hint
parsing so the prototype works anywhere.
"""
from __future__ import annotations

import re
from typing import Any

DEFAULT_FIELDS = ("title", "authors", "year", "journal", "doi", "isbn", "patent_no", "amount")


def extract_fields(text: str) -> dict[str, Any]:
    """Best-effort metadata extraction from raw OCR text."""
    fields: dict[str, Any] = {}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    year_match = re.search(r"\b(19|20)\d{2}\b", text)
    if year_match:
        fields["year"] = int(year_match.group(0))

    doi_match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", text, re.IGNORECASE)
    if doi_match:
        fields["doi"] = doi_match.group(0).strip(".")

    isbn_match = re.search(r"\b(?:ISBN[-: ]*)?((?:97[89][-\s]?)?\d[-\s]?\d{3}[-\s]?\d{2}[-\s]?\d[-\s]?\d{1})\b", text)
    if isbn_match:
        fields["isbn"] = re.sub(r"[-\s]", "", isbn_match.group(1))

    patent_match = re.search(r"\b(?:Patent[:\s]*|IN|US|EP)[-\s]*(\d{5,12})\b", text, re.IGNORECASE)
    if patent_match:
        fields["patent_no"] = patent_match.group(1)

    amount_match = re.search(r"₹\s*([\d,.]+)\s*(lakh|lacs|cr|crore)?", text)
    if amount_match:
        fields["amount_text"] = amount_match.group(0)

    if lines:
        fields["title"] = lines[0]
    return fields


def has_tesseract() -> bool:
    try:
        import shutil

        return shutil.which("tesseract") is not None
    except Exception:
        return False


def ocr_from_file(filename: str, content: bytes) -> dict[str, Any]:
    """Run OCR on an uploaded document. Falls back to hint-based extraction."""
    text = ""
    engine = "fallback"
    if has_tesseract():
        try:
            import pytesseract
            from PIL import Image

            import io

            image = Image.open(io.BytesIO(content))
            text = pytesseract.image_to_string(image)
            engine = "tesseract"
        except Exception:
            text = ""
    if not text.strip():
        text = _hint_text(filename)
        engine = "hint"
    fields = extract_fields(text)
    fields["_engine"] = engine
    fields["_unverified"] = True
    fields["_source_document"] = filename
    return fields


def _hint_text(filename: str) -> str:
    name = re.sub(r"\.(pdf|png|jpg|jpeg|tiff|bmp)$", "", filename, flags=re.IGNORECASE)
    return re.sub(r"[_-]", " ", name).strip()
