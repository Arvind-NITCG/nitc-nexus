#!/usr/bin/env python3
"""
PDF-to-JSON converter using pymupdf4llm + OpenRouter (Elephant model).

Usage:
    python main_llm.py <path_to_pdf>

Environment variables (loaded from .env):
    OPENROUTER_API_KEY – required
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from typing import Any

from dotenv import load_dotenv

load_dotenv()

import pymupdf4llm
import requests

# ── Configuration ────────────────────────────────────────────────────────────

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openrouter/elephant-alpha"

# ── Prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a document metadata extractor. You receive the markdown content of an academic PDF document and must return ONLY valid JSON matching the schema below. No extra text, no markdown fences, just raw JSON.

Schema:
{
  "title": "string - the document title",
  "category": "one of: syllabus | circular | academic_calendar | hostel_rules",
  "target_audience": "string - e.g. students, faculty, general",
  "date_issued": "string - dd/mm/yyyy format (e.g. 15/04/2024), or 'unknown' if not found"
}

Do NOT include the document content in the output. Only return the metadata fields above."""

USER_PROMPT_TEMPLATE = """Extract structured metadata from the following academic document.

Document:

{pdf_markdown}"""

# ── PDF → Markdown ───────────────────────────────────────────────────────────


def extract_markdown(path: str) -> str:
    """Convert a PDF to markdown using pymupdf4llm."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"PDF not found: {path}")

    md_text: str = pymupdf4llm.to_markdown(path)

    if not md_text.strip():
        raise ValueError("No extractable text found in the PDF.")

    return md_text


# ── LLM Call ─────────────────────────────────────────────────────────────────


def call_llm(markdown: str) -> str:
    """Send the markdown to OpenRouter Elephant and return the raw response."""
    if not OPENROUTER_API_KEY:
        raise EnvironmentError(
            "OPENROUTER_API_KEY is not set. Add it to your .env file."
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(pdf_markdown=markdown)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        print(f"  Calling {MODEL}…", file=sys.stderr)
        resp = requests.post(
            OPENROUTER_URL, headers=headers, json=payload, timeout=180
        )

        if resp.status_code == 429:
            wait = 2 ** attempt
            print(
                f"  [retry {attempt}/{max_retries}] Rate-limited. "
                f"Waiting {wait}s…",
                file=sys.stderr,
            )
            time.sleep(wait)
            continue

        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    raise requests.RequestException(
        f"Still rate-limited after {max_retries} retries. Try again later."
    )


# ── JSON Parsing ─────────────────────────────────────────────────────────────

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


def parse_json(text: str) -> dict[str, Any]:
    """Parse JSON from raw LLM output, handling markdown fences gracefully."""
    text = text.strip()

    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fenced code block
    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # First { … } substring
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError("LLM did not return valid JSON.\nRaw output:\n" + text)


# ── Date Normalisation ───────────────────────────────────────────────────────


def _normalize_date(raw: str) -> str:
    """Parse a raw date string and return it in dd/mm/yyyy format."""
    from datetime import datetime

    raw = raw.strip()
    if raw.lower() == "unknown":
        return "unknown"

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

    return raw


# ── Validation ───────────────────────────────────────────────────────────────

_VALID_CATEGORIES = {"syllabus", "circular", "academic_calendar", "hostel_rules"}


def validate(obj: dict[str, Any]) -> dict[str, Any]:
    """Ensure the LLM output matches the expected schema."""
    required = {"title", "category", "target_audience", "date_issued"}
    missing = required - obj.keys()
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    if obj["category"] not in _VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category '{obj['category']}'. "
            f"Must be one of {_VALID_CATEGORIES}."
        )

    # Normalise date to dd/mm/yyyy regardless of what the LLM returned
    obj["date_issued"] = _normalize_date(obj.get("date_issued", "unknown"))

    return obj


# ── Public API ───────────────────────────────────────────────────────────────


def process_pdf(path: str) -> dict[str, Any]:
    """
    End-to-end: PDF → pymupdf4llm markdown → LLM metadata extraction → validated JSON.
    """
    print(f"📄 Extracting markdown from {path}…", file=sys.stderr)
    md_text = extract_markdown(path)
    print(f"  ✔ Extracted {len(md_text)} chars of markdown", file=sys.stderr)

    print(f"🤖 Sending to {MODEL} for metadata extraction…", file=sys.stderr)
    raw = call_llm(md_text)
    result = parse_json(raw)
    result = validate(result)
    print("  ✔ LLM returned valid metadata", file=sys.stderr)

    # Attach the markdown we already have locally (saves LLM output tokens)
    result["content_markdown"] = md_text

    # Attach a locally-generated document_id
    result["document_id"] = str(uuid.uuid4())

    # Stable key order
    ordered: dict[str, Any] = {
        "document_id": result["document_id"],
        "title": result["title"],
        "category": result["category"],
        "target_audience": result["target_audience"],
        "date_issued": result["date_issued"],
        "content_markdown": result["content_markdown"],
    }
    return ordered


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python main_llm.py <path_to_pdf>", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]

    try:
        result = process_pdf(pdf_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except EnvironmentError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"LLM request failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"Processing error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Default output path: same name as PDF but .json, in CWD
    default_name = os.path.splitext(os.path.basename(pdf_path))[0] + ".json"
    default_path = os.path.join(os.getcwd(), default_name)

    save_path = input(f"Save JSON to [{default_path}]: ").strip()
    if not save_path:
        save_path = default_path

    os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✔ Saved to {save_path}")


if __name__ == "__main__":
    main()
