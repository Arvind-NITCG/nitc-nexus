#!/usr/bin/env python3
"""
PDF-to-JSON converter using pymupdf4llm (no LLM required).

Usage:
    python main.py <path_to_pdf>
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from typing import Any

import pymupdf4llm


# ── Category Detection ───────────────────────────────────────────────────────

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "syllabus": ["syllabus", "course structure", "curriculum", "credit"],
    "circular": ["circular", "notice", "memorandum", "office order"],
    "academic_calendar": ["academic calendar", "semester schedule", "examination schedule"],
    "hostel_rules": ["hostel", "mess", "hostel rules", "hostel regulation"],
}


def _detect_category(text: str) -> str:
    """Guess the document category from keyword frequency."""
    lower = text.lower()
    best, best_count = "circular", 0  # default fallback
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        count = sum(lower.count(kw) for kw in keywords)
        if count > best_count:
            best, best_count = cat, count
    return best


# ── Heuristic Metadata Extraction ───────────────────────────────────────────

_DATE_RE = re.compile(
    r"""
    (?:\d{4}[-/]\d{1,2}[-/]\d{1,2})     # YYYY-MM-DD or YYYY/MM/DD
    |(?:\d{1,2}[-/]\d{1,2}[-/]\d{4})     # DD-MM-YYYY or DD/MM/YYYY
    |(?:\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*,?\s*\d{4})  # 12 Jan 2024
    |(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\s*,?\s*\d{4})  # Jan 12, 2024
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _extract_title(md_text: str) -> str:
    """Pull the first markdown heading or the first non-empty line as title."""
    for line in md_text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Markdown heading
        if line.startswith("#"):
            return line.lstrip("#").strip()
        # First non-empty line as fallback
        return line[:120]
    return "Untitled"


def _normalize_date(raw: str) -> str:
    """Parse a raw date string and return it in dd/mm/yyyy format."""
    from datetime import datetime

    raw = raw.strip()

    # Try common formats in order
    formats = [
        "%Y-%m-%d",       # 2024-01-12
        "%Y/%m/%d",       # 2024/01/12
        "%d-%m-%Y",       # 12-01-2024
        "%d/%m/%Y",       # 12/01/2024
        "%d %B %Y",       # 12 January 2024
        "%d %b %Y",       # 12 Jan 2024
        "%d %B, %Y",      # 12 January, 2024
        "%d %b, %Y",      # 12 Jan, 2024
        "%B %d, %Y",      # January 12, 2024
        "%b %d, %Y",      # Jan 12, 2024
        "%B %d %Y",       # January 12 2024
        "%b %d %Y",       # Jan 12 2024
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            continue

    # If nothing worked, return the raw string as-is
    return raw


def _extract_date(text: str) -> str:
    """Find the first date-like string in the document and return it as dd/mm/yyyy."""
    match = _DATE_RE.search(text)
    if not match:
        return "unknown"
    return _normalize_date(match.group(0))


def _extract_audience(text: str) -> str:
    """Simple heuristic to guess target audience."""
    lower = text.lower()
    if any(kw in lower for kw in ["student", "undergraduate", "postgraduate", "b.tech", "m.tech"]):
        return "students"
    if any(kw in lower for kw in ["faculty", "professor", "teacher", "staff"]):
        return "faculty"
    return "general"


# ── Public API ───────────────────────────────────────────────────────────────


def process_pdf(path: str) -> dict[str, Any]:
    """
    Convert a PDF to structured JSON using pymupdf4llm.

    Returns a dict with keys:
        document_id, title, category, target_audience,
        date_issued, content_markdown
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"PDF not found: {path}")

    # pymupdf4llm converts PDF pages into clean markdown chunks
    md_chunks = pymupdf4llm.to_markdown(path, page_chunks=True)

    if not md_chunks:
        raise ValueError("No extractable text found in the PDF.")
        
    md_text = "\n\n".join(chunk.get("text", "") for chunk in md_chunks)

    title = _extract_title(md_text)
    category = _detect_category(md_text)
    audience = _extract_audience(md_text)
    date_issued = _extract_date(md_text)

    content_markdown = [{"page": i + 1, "text": chunk.get("text", "")} for i, chunk in enumerate(md_chunks)]

    result: dict[str, Any] = {
        "document_id": str(uuid.uuid4()),
        "title": title,
        "category": category,
        "target_audience": audience,
        "date_issued": date_issued,
        "content_markdown": content_markdown,
    }
    return result


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_pdf>", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]

    try:
        result = process_pdf(pdf_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"Processing error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Default output path: same name as the PDF but with .json extension, in CWD
    default_name = os.path.splitext(os.path.basename(pdf_path))[0] + ".json"
    default_path = os.path.join(os.getcwd(), default_name)

    save_path = input(f"Save JSON to [{default_path}]: ").strip()
    if not save_path:
        save_path = default_path

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✔ Saved to {save_path}")


if __name__ == "__main__":
    main()
