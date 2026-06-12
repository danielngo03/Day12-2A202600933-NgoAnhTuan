from __future__ import annotations

import random
from typing import Any

import pandas as pd

from core.utils import write_json, normalize_whitespace, compact_join


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build evaluation samples from the cleaned paper DataFrame."""
    if df.empty or len(df) < 3:
        raise ValueError(f"Not enough documents to build test set (got {len(df)}, need at least 3).")

    rng = random.Random(42)
    samples: list[dict[str, Any]] = []
    # Pick up to 12 diverse papers
    n = min(len(df), 12)
    selected = df.sample(n=n, random_state=42).reset_index(drop=True)

    for i, row in selected.iterrows():
        paper_id = str(row["paper_id"])
        title = str(row["title"])
        summary = str(row.get("summary", "") or "")
        authors_joined = str(row.get("authors_joined", "") or "")
        published = str(row.get("published", "") or "")
        categories_joined = str(row.get("categories_joined", "") or "")

        # 1. Summary question
        if summary:
            samples.append({
                "id": f"q{len(samples)+1:03d}",
                "question_type": "summary",
                "question": f"What is the paper '{title}' about?",
                "ground_truth": (summary[:300] + "..." if len(summary) > 300 else summary),
                "ground_truth_doc_ids": [paper_id],
            })

        # 2. Authors question
        if authors_joined:
            samples.append({
                "id": f"q{len(samples)+1:03d}",
                "question_type": "authors",
                "question": f"Who authored the paper '{title}'?",
                "ground_truth": authors_joined,
                "ground_truth_doc_ids": [paper_id],
            })

        # 3. Date question
        if published:
            samples.append({
                "id": f"q{len(samples)+1:03d}",
                "question_type": "date",
                "question": f"When was '{title}' published?",
                "ground_truth": published,
                "ground_truth_doc_ids": [paper_id],
            })

        # 4. Categories question
        if categories_joined:
            samples.append({
                "id": f"q{len(samples)+1:03d}",
                "question_type": "categories",
                "question": f"What categories does '{title}' belong to?",
                "ground_truth": categories_joined,
                "ground_truth_doc_ids": [paper_id],
            })

    # Limit to reasonable eval set
    samples = samples[:40]
    write_json(output_path, samples)
    print(f"[testset] Built {len(samples)} evaluation samples → {output_path}")
    return samples
