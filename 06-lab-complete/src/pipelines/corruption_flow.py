from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import write_csv, write_json, read_json, now_utc
from ingestion.crossref import load_raw_records, fetch_source_records
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from evaluation.metrics import evaluate_pipeline
from observability.quality import run_data_quality_checks, build_freshness_report
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Corruption → evaluate → repair → compare pipeline."""
    settings = load_settings()
    run_date = now_utc()
    print(f"\n{'='*60}")
    print(f"  Lab10 – Corruption & Repair Flow")
    print(f"  Run date: {run_date.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    # ── Step 1: Load baseline metrics and clean dataset ──────────────
    print("[corruption] Loading baseline metrics…")
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    print(f"[corruption] Baseline retrieval hit rate: {baseline_metrics.get('retrieval_hit_rate', 'N/A')}")

    print("[corruption] Loading clean baseline dataset…")
    import ast
    df_clean = pd.read_csv(settings.paths.clean_csv)
    # Restore list columns
    for col in ["authors", "categories"]:
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) and x.startswith("[") else []
            )

    # ── Step 2: Create corrupted dataset ─────────────────────────────
    print("[corruption] Corrupting dataset…")
    df_corrupted = corrupt_clean_dataframe(df_clean, settings.paths.corruption_log)

    # ── Step 3: Save corrupted artifacts ─────────────────────────────
    write_csv(df_corrupted, settings.paths.corrupted_clean_csv)
    write_json(
        settings.paths.corrupted_clean_json,
        df_corrupted.to_dict(orient="records"),
    )
    print(f"[corruption] Corrupted CSV → {settings.paths.corrupted_clean_csv}")

    # ── Step 4: Rebuild index on corrupted data & evaluate ───────────
    print("[corruption] Building corrupted embedding index…")
    corrupted_index = LocalEmbeddingIndex.build(
        df=df_corrupted,
        settings=settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    print("[corruption] Evaluating corrupted pipeline…")
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    print(f"[corruption] Corrupted metrics: {corrupted_bundle.summary}")

    # ── Step 5: Quality & freshness on corrupted data ────────────────
    print("[corruption] Quality checks on corrupted data…")
    corrupted_quality = run_data_quality_checks(df_corrupted, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        df_corrupted, settings, settings.paths.quality_dir / "corrupted_freshness.json"
    )

    # ── Step 6: Repair from raw records ──────────────────────────────
    print("[corruption] Repairing from raw source records…")
    raw_path = settings.paths.raw_records_json
    if raw_path.exists():
        raw_records = load_raw_records(raw_path)
    else:
        print("[corruption] Raw records not found, re-fetching from API…")
        raw_records = fetch_source_records(settings)

    df_repaired = build_clean_dataframe(raw_records, run_date)
    write_csv(df_repaired, settings.paths.repaired_clean_csv)
    write_json(
        settings.paths.repaired_clean_json,
        df_repaired.to_dict(orient="records"),
    )
    print(f"[corruption] Repaired CSV → {settings.paths.repaired_clean_csv}")

    # ── Step 7: Evaluate repaired dataset ────────────────────────────
    print("[corruption] Building repaired embedding index…")
    repaired_index = LocalEmbeddingIndex.build(
        df=df_repaired,
        settings=settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    print("[corruption] Evaluating repaired pipeline…")
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    print(f"[corruption] Repaired metrics: {repaired_bundle.summary}")

    # ── Step 8: Quality & freshness on repaired data ─────────────────
    repaired_quality = run_data_quality_checks(df_repaired, settings, "repaired")
    repaired_freshness = build_freshness_report(
        df_repaired, settings, settings.paths.quality_dir / "repaired_freshness.json"
    )

    # ── Step 9: Generate comparison report ───────────────────────────
    print("[corruption] Generating comparison report…")
    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )

    print(f"\n{'='*60}")
    print("  Corruption Flow COMPLETE ✅")
    print(f"  Baseline   hit rate: {baseline_metrics.get('retrieval_hit_rate', 0):.1%}")
    print(f"  Corrupted  hit rate: {corrupted_bundle.summary.get('retrieval_hit_rate', 0):.1%}")
    print(f"  Repaired   hit rate: {repaired_bundle.summary.get('retrieval_hit_rate', 0):.1%}")
    print(f"  Report: {settings.paths.comparison_report}")
    print(f"{'='*60}\n")
