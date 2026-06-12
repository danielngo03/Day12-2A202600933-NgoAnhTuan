from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(
    df: pd.DataFrame, settings: Settings, report_name: str
) -> dict[str, Any]:
    """Run data quality checks and save report to data/quality/."""
    checks: list[dict[str, Any]] = []

    def _check(name: str, passed: bool, details: str = "") -> None:
        checks.append({"check": name, "passed": passed, "details": details})

    total_rows = len(df)
    _check("row_count_positive", total_rows > 0, f"rows={total_rows}")
    _check("row_count_minimum", total_rows >= 5, f"rows={total_rows} (min=5)")

    # paper_id checks
    if "paper_id" in df.columns:
        null_ids = int(df["paper_id"].isna().sum())
        _check("paper_id_not_null", null_ids == 0, f"null_ids={null_ids}")
        dup_ids = int(df["paper_id"].duplicated().sum())
        _check("paper_id_unique", dup_ids == 0, f"duplicate_ids={dup_ids}")
    else:
        _check("paper_id_column_exists", False, "column missing")

    # title checks
    if "title" in df.columns:
        null_titles = int(df["title"].isna().sum())
        empty_titles = int((df["title"].fillna("").str.strip() == "").sum())
        _check("title_not_null", null_titles == 0, f"null={null_titles}")
        _check("title_not_empty", empty_titles == 0, f"empty={empty_titles}")
    else:
        _check("title_column_exists", False, "column missing")

    # summary quality
    if "summary_chars" in df.columns:
        short = int((df["summary_chars"].fillna(0) < 50).sum())
        _check("summary_length_adequate", short == 0, f"short_summaries={short}")
    elif "summary" in df.columns:
        short = int((df["summary"].fillna("").str.len() < 50).sum())
        _check("summary_length_adequate", short == 0, f"short_summaries={short}")

    # freshness
    if "age_days" in df.columns:
        stale = int((df["age_days"].fillna(9999) > settings.freshness_threshold_days).sum())
        pct_fresh = round((total_rows - stale) / max(total_rows, 1) * 100, 1)
        _check(
            "freshness_threshold",
            pct_fresh >= 50,
            f"stale_rows={stale}/{total_rows} ({pct_fresh}% fresh, threshold={settings.freshness_threshold_days}d)",
        )

    # text_for_embedding
    if "text_for_embedding" in df.columns:
        no_embed = int((df["text_for_embedding"].fillna("").str.strip() == "").sum())
        _check("text_for_embedding_populated", no_embed == 0, f"empty={no_embed}")

    passed = sum(1 for c in checks if c["passed"])
    failed = len(checks) - passed
    report: dict[str, Any] = {
        "report_name": report_name,
        "total_rows": total_rows,
        "total_checks": len(checks),
        "passed": passed,
        "failed": failed,
        "checks": checks,
    }

    quality_dir = settings.paths.quality_dir
    quality_dir.mkdir(parents=True, exist_ok=True)
    out_path = quality_dir / f"{report_name}_quality.json"
    write_json(out_path, report)
    print(f"[quality] {passed}/{len(checks)} checks passed → {out_path}")
    return report


def build_freshness_report(
    df: pd.DataFrame, settings: Settings, report_path
) -> dict[str, Any]:
    """Build a freshness summary report and save as JSON."""
    total_rows = len(df)

    if "published" not in df.columns or total_rows == 0:
        report = {
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "total_rows": total_rows,
            "is_fresh": False,
            "freshness_threshold_days": settings.freshness_threshold_days,
        }
    else:
        dates = df["published"].replace("", None).dropna()
        latest_published = str(dates.max()) if not dates.empty else None
        oldest_published = str(dates.min()) if not dates.empty else None

        stale_rows = 0
        if "age_days" in df.columns:
            stale_rows = int((df["age_days"].fillna(9999) > settings.freshness_threshold_days).sum())
        
        is_fresh = (stale_rows / max(total_rows, 1)) < 0.5

        report = {
            "latest_published": latest_published,
            "oldest_published": oldest_published,
            "stale_rows": stale_rows,
            "total_rows": total_rows,
            "is_fresh": is_fresh,
            "freshness_threshold_days": settings.freshness_threshold_days,
        }

    write_json(report_path, report)
    print(f"[freshness] Report → {report_path} (is_fresh={report['is_fresh']})")
    return report
