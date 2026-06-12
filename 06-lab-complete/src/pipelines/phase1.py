from __future__ import annotations

from datetime import UTC, datetime

from core.config import load_settings
from core.utils import write_csv, write_json, read_json, now_utc
from ingestion.crossref import fetch_source_records, load_raw_records
from ingestion.cleaning import build_clean_dataframe
from evaluation.testset import build_test_set
from evaluation.metrics import evaluate_pipeline
from observability.quality import run_data_quality_checks, build_freshness_report
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


def main() -> None:
    """Baseline pipeline: fetch → clean → index → eval → quality → report."""
    settings = load_settings()
    run_date = now_utc()
    print(f"\n{'='*60}")
    print(f"  Lab10 Phase 1 – Baseline Pipeline")
    print(f"  Run date: {run_date.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    # ── Step 1: Load or fetch raw records ────────────────────────────
    raw_path = settings.paths.raw_records_json
    if raw_path.exists() and not settings.refresh_source:
        print("[phase1] Loading cached raw records…")
        records = load_raw_records(raw_path)
    else:
        print("[phase1] Fetching fresh data from Crossref API…")
        records = fetch_source_records(settings)
    print(f"[phase1] Raw records: {len(records)}")

    # ── Step 2: Clean ────────────────────────────────────────────────
    print("[phase1] Cleaning data…")
    df = build_clean_dataframe(records, run_date)
    print(f"[phase1] Clean records: {len(df)}")
    if df.empty:
        raise RuntimeError("Cleaning produced an empty dataset – cannot continue.")

    # ── Step 3: Save clean CSV/JSON ──────────────────────────────────
    write_csv(df, settings.paths.clean_csv)
    # Store JSON-serializable version (convert list columns)
    df_json = df.copy()
    for col in ["authors", "categories"]:
        if col in df_json.columns:
            df_json[col] = df_json[col].apply(lambda x: x if isinstance(x, list) else [])
    write_json(settings.paths.clean_json, df_json.to_dict(orient="records"))
    print(f"[phase1] Clean CSV → {settings.paths.clean_csv}")
    print(f"[phase1] Clean JSON → {settings.paths.clean_json}")

    # ── Step 4: Build ChromaDB embedding index ────────────────────────
    print("[phase1] Building embedding index…")
    index = LocalEmbeddingIndex.build(
        df=df,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )
    print(f"[phase1] Index built: {len(index.documents)} documents")

    # ── Step 5: Create or load evaluation test set ───────────────────
    testset_path = settings.paths.eval_testset
    if testset_path.exists() and not settings.refresh_test_set:
        print(f"[phase1] Loading existing test set from {testset_path}…")
    else:
        print("[phase1] Building new evaluation test set…")
        build_test_set(df, testset_path)

    # ── Step 6: Evaluate ─────────────────────────────────────────────
    print("[phase1] Running evaluation…")
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=testset_path,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    print(f"[phase1] Evaluation complete: {bundle.summary}")

    # ── Step 7: Data quality checks ──────────────────────────────────
    print("[phase1] Running data quality checks…")
    quality = run_data_quality_checks(df, settings, "baseline")

    # ── Step 8: Freshness report ─────────────────────────────────────
    print("[phase1] Building freshness report…")
    freshness = build_freshness_report(df, settings, settings.paths.freshness_report)

    # ── Step 9: Markdown report ───────────────────────────────────────
    print("[phase1] Generating markdown report…")
    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "max_results": settings.max_results,
        "records_fetched": len(records),
        "records_clean": len(df),
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
    )

    # ── Step 10: Optional demo agent questions ────────────────────────
    demo_questions = [
        "What are the main topics covered in the corpus?",
        "Which papers discuss retrieval augmented generation?",
    ]
    demo_answers = []
    for q in demo_questions:
        try:
            result = answer_question(q, settings=settings, index=index)
            demo_answers.append({"question": q, "answer": result.answer, "sources": result.retrieved_titles})
        except Exception as exc:
            demo_answers.append({"question": q, "answer": f"Error: {exc}", "sources": []})
    write_json(settings.paths.demo_answers, demo_answers)

    print(f"\n{'='*60}")
    print("  Phase 1 COMPLETE ✅")
    print(f"  Retrieval hit rate : {bundle.summary.get('retrieval_hit_rate', 0):.1%}")
    print(f"  Mean token F1      : {bundle.summary.get('mean_token_f1', 0):.1%}")
    print(f"  Judge accuracy     : {bundle.summary.get('judge_accuracy', 0):.1%}")
    print(f"  Report             : {settings.paths.baseline_report}")
    print(f"{'='*60}\n")
