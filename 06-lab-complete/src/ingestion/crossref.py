from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import requests

from core.config import Settings
from core.utils import write_json, read_json, normalize_whitespace, compact_join

CROSSREF_API_URL = "https://api.crossref.org/works"
_RETRY_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, list):
        return normalize_whitespace(" ".join(str(v) for v in value if v))
    return normalize_whitespace(str(value))


def _parse_date(parts: list[list[int]] | None) -> str:
    """Convert Crossref date-parts [[YYYY, MM, DD]] to ISO string."""
    if not parts or not parts[0]:
        return ""
    date_parts = parts[0]
    year = date_parts[0] if len(date_parts) > 0 else 0
    month = date_parts[1] if len(date_parts) > 1 else 1
    day = date_parts[2] if len(date_parts) > 2 else 1
    try:
        return f"{year:04d}-{month:02d}-{day:02d}"
    except (TypeError, ValueError):
        return ""


def _parse_authors(item: dict) -> list[str]:
    authors_raw = item.get("author") or []
    names = []
    for author in authors_raw:
        given = _safe_str(author.get("given", ""))
        family = _safe_str(author.get("family", ""))
        name = f"{given} {family}".strip()
        if name:
            names.append(name)
    return names


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref API payload into list of PaperRecord."""
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []
    for item in items:
        doi = _safe_str(item.get("DOI", ""))
        if not doi:
            continue

        # Title
        title_raw = item.get("title") or []
        title = _safe_str(title_raw[0] if title_raw else "")
        if not title:
            continue

        # Abstract/summary
        abstract = _safe_str(item.get("abstract", ""))
        # Strip HTML tags (Crossref often returns JATS/HTML)
        import re
        abstract = re.sub(r"<[^>]+>", " ", abstract)
        abstract = normalize_whitespace(abstract)

        authors = _parse_authors(item)
        subjects = [_safe_str(s) for s in (item.get("subject") or []) if s]
        primary_category = subjects[0] if subjects else "uncategorized"

        # Dates
        published_date = _parse_date(
            item.get("published", {}).get("date-parts")
            or item.get("published-print", {}).get("date-parts")
            or item.get("published-online", {}).get("date-parts")
        )
        updated_date = _parse_date(item.get("indexed", {}).get("date-parts"))

        abs_url = f"https://doi.org/{doi}"
        pdf_url = ""
        for link in (item.get("link") or []):
            if "pdf" in link.get("content-type", "").lower() or "pdf" in link.get("URL", "").lower():
                pdf_url = link.get("URL", "")
                break

        records.append(PaperRecord(
            paper_id=doi,
            title=title,
            summary=abstract,
            authors=authors,
            categories=subjects,
            primary_category=primary_category,
            published=published_date,
            updated=updated_date,
            abs_url=abs_url,
            pdf_url=pdf_url,
            comment="",
        ))
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch papers from Crossref API, save raw response and parsed records."""
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "sort": "published",
        "order": "desc",
        "select": "DOI,title,abstract,author,subject,published,published-print,published-online,indexed,link",
    }

    payload: dict = {}
    last_exc: Exception | None = None
    for attempt in range(5):
        try:
            resp = requests.get(CROSSREF_API_URL, params=params, timeout=30)
            if resp.status_code in _RETRY_CODES:
                wait = 2 ** attempt
                time.sleep(wait)
                continue
            resp.raise_for_status()
            payload = resp.json()
            break
        except Exception as exc:
            last_exc = exc
            time.sleep(2 ** attempt)
    else:
        if last_exc:
            raise RuntimeError(f"Failed to fetch Crossref data after retries: {last_exc}") from last_exc

    # Save raw response
    raw_response_path = settings.paths.raw_api_response
    write_json(raw_response_path, payload)
    print(f"[crossref] Raw API response saved → {raw_response_path}")

    # Parse
    records = parse_crossref_payload(payload)
    print(f"[crossref] Parsed {len(records)} records from Crossref.")

    # Save raw records
    raw_records_path = settings.paths.raw_records_json
    write_json(raw_records_path, [asdict(r) for r in records])
    print(f"[crossref] Raw records saved → {raw_records_path}")

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load JSON snapshot of raw records back into PaperRecord instances."""
    data = read_json(path)
    records = []
    for item in data:
        records.append(PaperRecord(
            paper_id=item.get("paper_id", ""),
            title=item.get("title", ""),
            summary=item.get("summary", ""),
            authors=item.get("authors") or [],
            categories=item.get("categories") or [],
            primary_category=item.get("primary_category", ""),
            published=item.get("published", ""),
            updated=item.get("updated", ""),
            abs_url=item.get("abs_url", ""),
            pdf_url=item.get("pdf_url", ""),
            comment=item.get("comment", ""),
        ))
    return records
