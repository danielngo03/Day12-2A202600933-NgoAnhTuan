# Pha 1 – Báo cáo Baseline Pipeline

## 1. Tóm tắt Nguồn Dữ liệu

- **API nguồn**: Crossref REST API
- **Truy vấn (Query)**: `agentic retrieval augmented generation large language model`
- **Bộ lọc (Filter)**: `from-pub-date:2025-12-12,has-abstract:true`
- **Số kết quả tối đa yêu cầu**: 24
- **Số bản ghi đã tải**: 24
- **Số bản ghi sau khi làm sạch**: 24

## 2. Chỉ số Đánh giá (Evaluation Metrics)

| Chỉ số | Giá trị |
|--------|---------|
| Tỷ lệ tìm kiếm chính xác (retrieval_hit_rate) | 1.0000 |
| Điểm F1-Token trung bình (mean_token_f1) | 0.9270 |
| Độ chính xác của Giám khảo (judge_accuracy) | 0.9722 |
| Điểm Giám khảo trung bình (mean_judge_score) | 4.3333 |
| Số mẫu thử nghiệm (samples) | 36 |


## 3. Chất lượng Dữ liệu (Data Quality)

**Tổng số dòng**: 24 | **Lượt kiểm tra**: Đạt 9/9

| Tên kiểm tra | Trạng thái | Chi tiết |
|--------------|------------|----------|
| Số dòng dương (>0) | ✅ Đạt | rows=24 |
| Số dòng tối thiểu (>=5) | ✅ Đạt | rows=24 (min=5) |
| Mã bài báo không null | ✅ Đạt | null_ids=0 |
| Mã bài báo duy nhất | ✅ Đạt | duplicate_ids=0 |
| Tiêu đề không null | ✅ Đạt | null=0 |
| Tiêu đề không trống | ✅ Đạt | empty=0 |
| Độ dài tóm tắt đầy đủ (>=50 ký tự) | ✅ Đạt | short_summaries=0 |
| Độ tươi trong ngưỡng cho phép | ✅ Đạt | stale_rows=0/24 (100.0% fresh, threshold=180d) |
| Dữ liệu text embedding đầy đủ | ✅ Đạt | empty=0 |


## 4. Độ tươi của Dữ liệu (Freshness)

- **Ngày xuất bản mới nhất**: 2027-05-07
- **Ngày xuất bản cũ nhất**: 2026-12-01
- **Số dòng bị cũ (Stale)**: 0 / 24
- **Ngưỡng độ tươi**: 180 ngày
- **Đạt yêu cầu độ tươi**: ✅ Đạt (Có)
