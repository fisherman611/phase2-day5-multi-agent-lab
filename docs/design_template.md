# Design Template

## Problem

Xây dựng một research assistant nhận câu hỏi phức tạp, tự điều phối nhiều bước để:
- Thu thập nguồn tham khảo liên quan.
- Rút trích và phân tích luận điểm chính.
- Tổng hợp câu trả lời cuối có cấu trúc và tham chiếu nguồn.

Hệ thống cần chạy ổn định ngay cả khi thiếu API key hoặc provider lỗi tạm thời.

## Why multi-agent?

Single-agent thường làm tốt câu hỏi ngắn, nhưng với bài toán research dài sẽ gặp:
- Prompt quá tải: vừa tìm nguồn, vừa phân tích, vừa viết trong một lần gọi.
- Khó debug: không biết lỗi nằm ở bước thu thập dữ liệu hay bước tổng hợp.
- Khó kiểm soát chất lượng: thiếu checkpoint giữa các bước.

Multi-agent tách rõ vai trò giúp:
- Giảm coupling giữa các nhiệm vụ (search, analysis, writing).
- Dễ trace theo từng bước để đo lỗi/latency.
- Dễ mở rộng policy định tuyến và guardrail.

## Agent roles

| Agent | Responsibility | Input | Output | Failure mode |
|---|---|---|---|---|
| Supervisor | Quyết định agent tiếp theo hoặc dừng workflow | `request`, `sources`, `research_notes`, `analysis_notes`, `final_answer`, `errors`, `iteration` | Route tiếp theo: `researcher` / `analyst` / `writer` / `critic` / `done` | Route sai thứ tự hoặc lặp vô hạn nếu policy không có stop condition |
| Researcher | Thu thập nguồn và tạo ghi chú research | `request.query`, `request.max_sources` | `sources`, `research_notes`, `agent_results` | Search provider lỗi, nguồn kém chất lượng, thiếu citation markers |
| Analyst | Chuyển research notes thành insight có cấu trúc | `research_notes`, `request.query` | `analysis_notes`, `agent_results` | Phân tích nông, không nêu uncertainty/gaps |
| Writer | Tổng hợp câu trả lời cuối | `research_notes`, `analysis_notes`, `sources`, `request.audience` | `final_answer`, `agent_results` | Câu trả lời thiếu chiều sâu, thiếu reference map |
| Critic (optional) | Kiểm tra heuristic về citation/độ đầy đủ | `final_answer`, `sources` | Findings trong `agent_results` và `trace` | False positive/false negative do rule-based check đơn giản |

## Shared state

Các field chính trong `ResearchState` và lý do:
- `request`: giữ query, audience, max_sources để mọi agent dùng cùng ngữ cảnh.
- `iteration`: đếm vòng lặp workflow để enforce guardrail.
- `route_history`: lưu quyết định routing để debug điều phối.
- `sources`: danh sách `SourceDocument` cho researcher/writer/critic.
- `research_notes`: đầu ra trung gian từ researcher.
- `analysis_notes`: đầu ra trung gian từ analyst.
- `final_answer`: output cuối.
- `agent_results`: log nội dung chính + metadata token theo từng agent.
- `trace`: event-level trace phục vụ kiểm thử và phân tích lỗi.
- `errors`: gom lỗi theo từng bước để fallback và tính failure rate.

## Routing policy

Mô tả policy hiện tại:
- Nếu `iteration >= max_iterations` -> `done`.
- Nếu thiếu `sources` hoặc `research_notes` -> `researcher`.
- Nếu đã có research nhưng thiếu `analysis_notes` -> `analyst`.
- Nếu thiếu `final_answer` -> `writer`.
- Nếu bật critic và critic chưa chạy -> `critic`.
- Còn lại -> `done`.

Luồng graph chuẩn:

```text
START -> supervisor
supervisor -> researcher -> supervisor
supervisor -> analyst    -> supervisor
supervisor -> writer     -> supervisor
supervisor -> critic     -> supervisor   (optional)
supervisor -> END (done)
```

## Guardrails

- Max iterations: dùng `MAX_ITERATIONS` (mặc định 6), supervisor dừng khi đạt ngưỡng.
- Timeout: `TIMEOUT_SECONDS` dùng cho call search provider (Tavily).
- Retry: hiện chưa có exponential retry chuẩn cho LLM/search; cần mở rộng bằng `tenacity`.
- Fallback:
  - Search: lỗi Tavily -> fallback mock sources.
  - LLM: lỗi provider/missing key -> fallback notes/analysis/answer nội bộ.
  - Workflow: nếu graph backend unavailable -> fallback loop executor.
- Validation:
  - Schema bằng Pydantic cho request/state/metrics.
  - Critic heuristic check citation markers và độ dài answer.

## Benchmark plan

### Query set đề xuất
1. `Design a production GraphRAG system for a Vietnamese legal assistant...`
2. `Compare Multi-Agent RAG vs Single-Agent RAG for enterprise incident response...`
3. `Build a 90-day roadmap to deploy a multilingual healthcare research copilot...`

### Metrics
- `latency_seconds`: wall-clock từ lúc bắt đầu runner đến lúc có `ResearchState`.
- `estimated_cost_usd`: ước tính từ token metadata (nếu có).
- `quality_score` (0-10): heuristic score + peer rubric review.
- `citation_coverage` (0-1): tỷ lệ citation marker hợp lệ theo số nguồn.
- `failure_rate` (0-1): có lỗi trong `state.errors` hay không.

### Expected outcome
- Multi-agent có latency cao hơn baseline.
- Multi-agent có quality và citation coverage cao hơn baseline.
- Khi thiếu API key, hệ thống vẫn trả được output nhờ fallback (nhưng failure_rate tăng).
