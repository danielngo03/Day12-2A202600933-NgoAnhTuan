from __future__ import annotations

import random
import re
from typing import Any

import pandas as pd

from core.utils import write_json, normalize_whitespace


_NOISE_WORDS = [
    "CORRUPT", "ERROR", "MISSING", "INVALID", "NULL",
    "###", "???", "XXX", "REDACTED", "N/A",
]


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Simulate realistic data corruption scenarios on the clean DataFrame."""
    if df.empty:
        raise ValueError("Cannot corrupt an empty dataframe.")

    rng = random.Random(99)
    corrupted = df.copy()
    log: list[dict[str, Any]] = []

    n = len(corrupted)
    # --- 1. Drop some latest records (simulate data loss) ---
    n_drop = max(1, n // 5)
    # Sort by published desc to drop newest
    sorted_idx = corrupted.sort_values("published", ascending=False).index[:n_drop]
    drop_ids = corrupted.loc[sorted_idx, "paper_id"].tolist()
    corrupted = corrupted.drop(index=sorted_idx).reset_index(drop=True)
    log.append({"type": "drop_latest", "count": len(drop_ids), "paper_ids": drop_ids})

    n = len(corrupted)
    # --- 2. Blank summary on some rows ---
    n_blank = max(1, n // 6)
    blank_idx = rng.sample(list(range(n)), k=min(n_blank, n))
    corrupted.loc[blank_idx, "summary"] = ""
    corrupted.loc[blank_idx, "summary_chars"] = 0
    log.append({"type": "blank_summary", "count": len(blank_idx), "rows": blank_idx})

    # --- 3. Inject noise into summary on some rows ---
    n_noise = max(1, n // 5)
    noise_idx = rng.sample(list(range(n)), k=min(n_noise, n))
    for idx in noise_idx:
        noise_word = rng.choice(_NOISE_WORDS)
        original = str(corrupted.at[idx, "summary"])
        words = original.split()
        if words:
            insert_pos = rng.randint(0, len(words))
            words.insert(insert_pos, noise_word)
            corrupted.at[idx, "summary"] = " ".join(words)
        else:
            corrupted.at[idx, "summary"] = noise_word
    log.append({"type": "inject_noise", "count": len(noise_idx), "rows": noise_idx})

    # --- 4. Truncate title on some rows ---
    n_trunc = max(1, n // 6)
    trunc_idx = rng.sample(list(range(n)), k=min(n_trunc, n))
    for idx in trunc_idx:
        title = str(corrupted.at[idx, "title"])
        corrupted.at[idx, "title"] = title[:15] + "..."
    log.append({"type": "truncate_title", "count": len(trunc_idx), "rows": trunc_idx})

    # --- 5. Make publication dates stale (shift to ~3 years ago) ---
    n_stale = max(1, n // 5)
    stale_idx = rng.sample(list(range(n)), k=min(n_stale, n))
    for idx in stale_idx:
        published = str(corrupted.at[idx, "published"])
        m = re.match(r"(\d{4})", published)
        if m:
            old_year = int(m.group(1)) - 3
            corrupted.at[idx, "published"] = published.replace(m.group(1), str(old_year))
            if "age_days" in corrupted.columns and pd.notna(corrupted.at[idx, "age_days"]):
                corrupted.at[idx, "age_days"] = int(corrupted.at[idx, "age_days"]) + 365 * 3
    log.append({"type": "stale_dates", "count": len(stale_idx), "rows": stale_idx})

    # --- 6. Add duplicate rows ---
    n_dup = max(1, n // 8)
    dup_idx = rng.sample(list(range(n)), k=min(n_dup, n))
    dup_rows = corrupted.iloc[dup_idx].copy()
    corrupted = pd.concat([corrupted, dup_rows], ignore_index=True)
    log.append({"type": "add_duplicates", "count": len(dup_idx), "rows": dup_idx})

    # --- 7. Rebuild text_for_embedding ---
    def _rebuild_text(row: pd.Series) -> str:
        return (
            f"Title: {row.get('title', '')}\n"
            f"Authors: {row.get('authors_joined', '')}\n"
            f"Published: {row.get('published', '')}\n"
            f"Categories: {row.get('categories_joined', '')}\n"
            f"Summary: {row.get('summary', '')}"
        ).strip()

    corrupted["text_for_embedding"] = corrupted.apply(_rebuild_text, axis=1)

    write_json(output_log_path, {
        "total_rows_before": n,
        "total_rows_after": len(corrupted),
        "operations": log,
    })
    print(f"[corruption] Corrupted {n} → {len(corrupted)} rows. Log → {output_log_path}")
    return corrupted
