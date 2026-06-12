# Báo cáo So sánh Gây lỗi & Phục hồi dữ liệu (Corruption & Repair)

## Tóm tắt

Báo cáo này so sánh hiệu năng của pipeline RAG qua ba trạng thái dữ liệu khác nhau:
1. **Baseline** – Dữ liệu sạch, chuẩn thu được từ nguồn Crossref API ban đầu.
2. **Corrupted (Gây lỗi)** – Dữ liệu bị cố tình áp dụng các lỗi phổ biến (trùng lặp, thiếu trường, dữ liệu cũ...).
3. **Repaired (Phục hồi)** – Dữ liệu được khôi phục tự động từ cache raw ban đầu.

## So sánh Chỉ số Hiệu năng

| Chỉ số | Baseline (Chuẩn) | Corrupted (Lỗi) | Repaired (Phục hồi) | Δ (Phục hồi vs Baseline) |
|--------|------------------|-----------------|---------------------|--------------------------|
| Tỷ lệ tìm kiếm chính xác (retrieval_hit_rate) | 1.0000 | 0.7500 | 1.0000 | +0.0000 |
| Điểm F1-Token trung bình (mean_token_f1) | 0.9270 | 0.6742 | 0.9270 | +0.0000 |
| Độ chính xác của Giám khảo (judge_accuracy) | 0.9722 | 0.6944 | 0.9722 | +0.0000 |
| Điểm Giám khảo trung bình (mean_judge_score) | 4.3333 | 3.4444 | 4.3333 | +0.0000 |

## Đánh giá Chất lượng Dữ liệu

| Trạng thái | Kết quả kiểm tra chất lượng |
|------------|-----------------------------|
| Corrupted | Đạt 7/9 kiểm tra chất lượng |
| Repaired | Đạt 9/9 kiểm tra chất lượng |

## Đánh giá Độ tươi của Dữ liệu (Freshness)

| Trạng thái | Độ tươi dữ liệu |
|------------|-----------------|
| Corrupted | ✅ Đạt độ tươi (5/22 dòng bị cũ) |
| Repaired | ✅ Đạt độ tươi (0/24 dòng bị cũ) |

## Kết luận

Kết quả so sánh chứng minh rõ ràng rằng việc dữ liệu bị lỗi (data corruption) gây ra sự sụt giảm nghiêm trọng và đo lường được trên tất cả các chỉ số (tỷ lệ hit rate tìm kiếm, điểm F1-token và độ chính xác của LLM Judge). Khi áp dụng pipeline phục hồi (Repair) từ nguồn raw, tất cả các chỉ số chất lượng, độ tươi và chất lượng phản hồi của RAG Agent đều được khôi phục về mức tương đương mẫu chuẩn (Baseline). Điều này khẳng định vai trò thiết yếu của hệ thống giám sát khả năng quan sát dữ liệu (data observability) trong các hệ thống RAG thực tế.
