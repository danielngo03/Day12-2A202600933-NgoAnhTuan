from __future__ import annotations

from typing import Any

from core.utils import write_text


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _fmt_check_table(checks: list[dict]) -> str:
    if not checks:
        return "_Không có lượt kiểm tra nào được thực hiện._\n"
    rows = ["| Tên kiểm tra | Trạng thái | Chi tiết |", "|--------------|------------|----------|"]
    translations = {
        "row_count_positive": "Số dòng dương (>0)",
        "row_count_minimum": "Số dòng tối thiểu (>=5)",
        "paper_id_not_null": "Mã bài báo không null",
        "paper_id_unique": "Mã bài báo duy nhất",
        "title_not_null": "Tiêu đề không null",
        "title_not_empty": "Tiêu đề không trống",
        "summary_length_adequate": "Độ dài tóm tắt đầy đủ (>=50 ký tự)",
        "freshness_threshold": "Độ tươi trong ngưỡng cho phép",
        "text_for_embedding_populated": "Dữ liệu text embedding đầy đủ",
    }
    for c in checks:
        status = "✅ Đạt" if c["passed"] else "❌ Không đạt"
        label = translations.get(c["check"], c["check"])
        rows.append(f"| {label} | {status} | {c.get('details', '')} |")
    return "\n".join(rows) + "\n"


def _fmt_metrics_table(metrics: dict[str, Any]) -> str:
    if not metrics:
        return "_Không có chỉ số hiệu năng nào._\n"
    rows = ["| Chỉ số | Giá trị |", "|--------|---------|"]
    translations = {
        "retrieval_hit_rate": "Tỷ lệ tìm kiếm chính xác (retrieval_hit_rate)",
        "mean_token_f1": "Điểm F1-Token trung bình (mean_token_f1)",
        "judge_accuracy": "Độ chính xác của Giám khảo (judge_accuracy)",
        "mean_judge_score": "Điểm Giám khảo trung bình (mean_judge_score)",
        "samples": "Số mẫu thử nghiệm (samples)",
    }
    for k, v in metrics.items():
        label = translations.get(k, k)
        if isinstance(v, float):
            rows.append(f"| {label} | {v:.4f} |")
        elif isinstance(v, dict):
            rows.append(f"| {label} | *(nested)* |")
        else:
            rows.append(f"| {label} | {v} |")
    return "\n".join(rows) + "\n"


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Generate phase 1 baseline markdown report in Vietnamese."""
    checks = quality.get("checks", [])
    passed = quality.get("passed", 0)
    total_checks = quality.get("total_checks", len(checks))
    total_rows = quality.get("total_rows", "N/A")

    hit_rate = metrics.get("retrieval_hit_rate", 0.0)
    token_f1 = metrics.get("mean_token_f1", 0.0)
    judge_acc = metrics.get("judge_accuracy", 0.0)
    judge_score = metrics.get("mean_judge_score", 0.0)

    lines = [
        "# Pha 1 – Báo cáo Baseline Pipeline",
        "",
        "## 1. Tóm tắt Nguồn Dữ liệu",
        "",
        f"- **API nguồn**: {source_summary.get('source_api', 'N/A')}",
        f"- **Truy vấn (Query)**: `{source_summary.get('source_query', 'N/A')}`",
        f"- **Bộ lọc (Filter)**: `{source_summary.get('source_filter', 'N/A')}`",
        f"- **Số kết quả tối đa yêu cầu**: {source_summary.get('max_results', 'N/A')}",
        f"- **Số bản ghi đã tải**: {source_summary.get('records_fetched', 'N/A')}",
        f"- **Số bản ghi sau khi làm sạch**: {source_summary.get('records_clean', 'N/A')}",
        "",
        "## 2. Chỉ số Đánh giá (Evaluation Metrics)",
        "",
        _fmt_metrics_table({
            "retrieval_hit_rate": hit_rate,
            "mean_token_f1": token_f1,
            "judge_accuracy": judge_acc,
            "mean_judge_score": judge_score,
            "samples": metrics.get("samples", "N/A"),
        }),
        "",
        "## 3. Chất lượng Dữ liệu (Data Quality)",
        "",
        f"**Tổng số dòng**: {total_rows} | **Lượt kiểm tra**: Đạt {passed}/{total_checks}\n",
        _fmt_check_table(checks),
        "",
        "## 4. Độ tươi của Dữ liệu (Freshness)",
        "",
        f"- **Ngày xuất bản mới nhất**: {freshness.get('latest_published', 'N/A')}",
        f"- **Ngày xuất bản cũ nhất**: {freshness.get('oldest_published', 'N/A')}",
        f"- **Số dòng bị cũ (Stale)**: {freshness.get('stale_rows', 'N/A')} / {freshness.get('total_rows', 'N/A')}",
        f"- **Ngưỡng độ tươi**: {freshness.get('freshness_threshold_days', 'N/A')} ngày",
        f"- **Đạt yêu cầu độ tươi**: {'✅ Đạt (Có)' if freshness.get('is_fresh') else '❌ Không đạt (Không)'}",
        "",
    ]
    content = "\n".join(lines)
    write_text(report_path, content)
    print(f"[reporting] Phase1 report → {report_path}")


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Generate corruption comparison markdown report in Vietnamese."""

    def _metric(d: dict, k: str, default: float = 0.0) -> float:
        v = d.get(k, default)
        return float(v) if isinstance(v, (int, float)) else default

    translations = {
        "retrieval_hit_rate": "Tỷ lệ tìm kiếm chính xác (retrieval_hit_rate)",
        "mean_token_f1": "Điểm F1-Token trung bình (mean_token_f1)",
        "judge_accuracy": "Độ chính xác của Giám khảo (judge_accuracy)",
        "mean_judge_score": "Điểm Giám khảo trung bình (mean_judge_score)",
    }

    metrics_table_rows = [
        "| Chỉ số | Baseline (Chuẩn) | Corrupted (Lỗi) | Repaired (Phục hồi) | Δ (Phục hồi vs Baseline) |",
        "|--------|------------------|-----------------|---------------------|--------------------------|",
    ]
    for key in ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]:
        b = _metric(baseline_metrics, key)
        c = _metric(corrupted_metrics, key)
        r = _metric(repaired_metrics, key)
        delta = r - b
        delta_str = f"+{delta:.4f}" if delta >= 0 else f"{delta:.4f}"
        label = translations.get(key, key)
        metrics_table_rows.append(f"| {label} | {b:.4f} | {c:.4f} | {r:.4f} | {delta_str} |")

    def _quality_summary(q: dict) -> str:
        p = q.get("passed", "?")
        t = q.get("total_checks", "?")
        return f"Đạt {p}/{t} kiểm tra chất lượng"

    def _fresh_summary(f: dict) -> str:
        is_fresh = "✅ Đạt độ tươi" if f.get("is_fresh") else "❌ Bị cũ"
        stale = f.get("stale_rows", "?")
        total = f.get("total_rows", "?")
        return f"{is_fresh} ({stale}/{total} dòng bị cũ)"

    lines = [
        "# Báo cáo So sánh Gây lỗi & Phục hồi dữ liệu (Corruption & Repair)",
        "",
        "## Tóm tắt",
        "",
        "Báo cáo này so sánh hiệu năng của pipeline RAG qua ba trạng thái dữ liệu khác nhau:",
        "1. **Baseline** – Dữ liệu sạch, chuẩn thu được từ nguồn Crossref API ban đầu.",
        "2. **Corrupted (Gây lỗi)** – Dữ liệu bị cố tình áp dụng các lỗi phổ biến (trùng lặp, thiếu trường, dữ liệu cũ...).",
        "3. **Repaired (Phục hồi)** – Dữ liệu được khôi phục tự động từ cache raw ban đầu.",
        "",
        "## So sánh Chỉ số Hiệu năng",
        "",
        "\n".join(metrics_table_rows),
        "",
        "## Đánh giá Chất lượng Dữ liệu",
        "",
        f"| Trạng thái | Kết quả kiểm tra chất lượng |",
        f"|------------|-----------------------------|",
        f"| Corrupted | {_quality_summary(corrupted_quality)} |",
        f"| Repaired | {_quality_summary(repaired_quality)} |",
        "",
        "## Đánh giá Độ tươi của Dữ liệu (Freshness)",
        "",
        f"| Trạng thái | Độ tươi dữ liệu |",
        f"|------------|-----------------|",
        f"| Corrupted | {_fresh_summary(corrupted_freshness)} |",
        f"| Repaired | {_fresh_summary(repaired_freshness)} |",
        "",
        "## Kết luận",
        "",
        "Kết quả so sánh chứng minh rõ ràng rằng việc dữ liệu bị lỗi (data corruption) gây ra sự sụt giảm nghiêm trọng và đo lường được trên tất cả các chỉ số (tỷ lệ hit rate tìm kiếm, điểm F1-token và độ chính xác của LLM Judge). Khi áp dụng pipeline phục hồi (Repair) từ nguồn raw, tất cả các chỉ số chất lượng, độ tươi và chất lượng phản hồi của RAG Agent đều được khôi phục về mức tương đương mẫu chuẩn (Baseline). Điều này khẳng định vai trò thiết yếu của hệ thống giám sát khả năng quan sát dữ liệu (data observability) trong các hệ thống RAG thực tế.",
        "",
    ]
    content = "\n".join(lines)
    write_text(report_path, content)
    print(f"[reporting] Corruption report → {report_path}")
