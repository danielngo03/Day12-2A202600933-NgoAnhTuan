from __future__ import annotations

import re
from datetime import datetime, date

import pandas as pd

from core.utils import normalize_whitespace, compact_join
from ingestion.crossref import PaperRecord


def _clean_text(value: str) -> str:
    """Strip HTML, collapse whitespace."""
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    return normalize_whitespace(text)


def _parse_iso_date(value: str) -> date | None:
    """Try to parse YYYY-MM-DD or partial dates."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(value[:len(fmt.replace("%Y", "0000").replace("%m", "00").replace("%d", "00"))], fmt).date()
        except ValueError:
            pass
    # Try stripping to just year
    match = re.match(r"(\d{4})", value)
    if match:
        try:
            return date(int(match.group(1)), 1, 1)
        except ValueError:
            pass
    return None


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Build a clean, normalized DataFrame ready for embedding."""
    run_date_val = run_date.date() if isinstance(run_date, datetime) else run_date
    rows = []
    for rec in records:
        title = _clean_text(rec.title)
        if not title:
            continue
        summary = _clean_text(rec.summary)
        authors_list = [normalize_whitespace(a) for a in (rec.authors or []) if a]
        categories_list = [normalize_whitespace(c) for c in (rec.categories or []) if c]
        published_str = rec.published or ""
        published_date = _parse_iso_date(published_str)
        age_days: int | None = None
        if published_date:
            delta = run_date_val - published_date
            age_days = max(0, delta.days)
        authors_joined = compact_join(authors_list)
        categories_joined = compact_join(categories_list)
        summary_chars = len(summary)
        # Build rich text_for_embedding
        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {published_str}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
        ).strip()
        rows.append({
            "paper_id": rec.paper_id,
            "title": title,
            "summary": summary,
            "authors": authors_list,
            "authors_joined": authors_joined,
            "categories": categories_list,
            "categories_joined": categories_joined,
            "primary_category": normalize_whitespace(rec.primary_category or ""),
            "published": published_str,
            "updated": rec.updated or "",
            "abs_url": rec.abs_url or "",
            "pdf_url": rec.pdf_url or "",
            "age_days": age_days,
            "summary_chars": summary_chars,
            "text_for_embedding": text_for_embedding,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Drop duplicates by paper_id, keep most recent by published
    df = df.sort_values("published", ascending=False, na_position="last")
    df = df.drop_duplicates(subset=["paper_id"], keep="first")

    # Filter out rows with no summary
    df = df[df["summary_chars"] > 0].copy()

    # Sort by published desc, then paper_id
    df = df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    return df
