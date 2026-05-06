# Lab Guide: Multi-Agent Research System

## Scenario

Bạn cần xây dựng một research assistant có thể nhận câu hỏi dài, tìm thông tin, phân tích và viết câu trả lời cuối cùng. Lab yêu cầu so sánh hai cách làm:

1. **Single-agent baseline**: một agent làm toàn bộ.
2. **Multi-agent workflow**: Supervisor điều phối Researcher, Analyst, Writer.

## Quy tắc quan trọng

- Không thêm agent nếu không có lý do rõ ràng.
- Mỗi agent phải có responsibility riêng.
- Shared state phải đủ rõ để debug.
- Phải có trace hoặc log cho từng bước.
- Phải benchmark, không chỉ nhìn output bằng cảm tính.

## Milestone 1: Baseline

File gợi ý:

- `src/multi_agent_research_lab/cli.py`
- `src/multi_agent_research_lab/services/llm_client.py`

Trạng thái hiện tại:
- Baseline đã gọi `LLMClient` thật (NVIDIA endpoint qua `ChatNVIDIA`).
- Nếu thiếu key/provider lỗi thì baseline trả fallback message thay vì crash.

Việc cần làm thêm để production-ready:
- Thêm retry policy và timeout rõ ràng cho LLM call.
- Chuẩn hóa output format (JSON schema hoặc structured sections).

## Milestone 2: Supervisor

File gợi ý:

- `src/multi_agent_research_lab/agents/supervisor.py`
- `src/multi_agent_research_lab/graph/workflow.py`

Trạng thái hiện tại:
- Supervisor đã route theo thứ tự thiếu dữ liệu: `researcher -> analyst -> writer -> done`.
- Có guardrail `max_iterations`.
- Có fallback theo lỗi: nếu nhiều lỗi liên tiếp thì ưu tiên `writer` để kết thúc an toàn.
- Workflow hỗ trợ:
  - LangGraph runtime nếu import được.
  - Fallback loop executor nếu thiếu dependency.

Gợi ý câu hỏi thiết kế:

- Khi nào gọi Researcher?
- Khi nào gọi Analyst?
- Khi nào gọi Writer?
- Khi nào stop?
- Nếu agent fail thì retry hay fallback?

## Milestone 3: Worker agents

File gợi ý:

- `agents/researcher.py`
- `agents/analyst.py`
- `agents/writer.py`

Trạng thái hiện tại:
- `ResearcherAgent`: gọi `SearchClient`, tạo `sources` và `research_notes`.
- `AnalystAgent`: phân tích từ research notes thành claims/gaps/next steps.
- `WriterAgent`: tổng hợp final answer theo audience và references.
- `CriticAgent` (optional): check heuristic citation coverage/answer quality.

Lưu ý chất lượng:
- Prompt hiện tại là bản khởi điểm; cần tinh chỉnh thêm theo domain.
- Nếu muốn output ổn định hơn, nên chuyển sang structured outputs.

## Milestone 4: Trace và benchmark

File gợi ý:

- `observability/tracing.py`
- `evaluation/benchmark.py`
- `evaluation/report.py`

Trạng thái hiện tại:
- Tracing local có trong `state.trace`.
- Đã tích hợp gửi trace lên LangSmith nếu có:
  - `LANGSMITH_API_KEY`
  - `LANGSMITH_TRACING=true`
  - `LANGSMITH_ENDPOINT`
  - `LANGSMITH_PROJECT`
- Benchmark command đã có trong CLI: so sánh baseline vs multi-agent và xuất markdown report.

Benchmark tối thiểu:

| Metric | Cách đo gợi ý |
|---|---|
| Latency | wall-clock time |
| Cost | token usage hoặc provider usage |
| Quality | rubric 0-10 do peer review |
| Citation coverage | số claims có source / tổng claims chính |
| Failure rate | số query fail / tổng query |

## Cách chạy lab (thực hành)

### 1) Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -e "[dev,llm]"
cp .env.example .env
```

### 2) Cấu hình env tối thiểu

```bash
NVIDIA_API_KEY=...
NVIDIA_MODEL=meta/llama-3.1-8b-instruct
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
LANGSMITH_API_KEY=...
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_PROJECT=multi-agent
```

### 3) Smoke test

```bash
python -m multi_agent_research_lab.cli --help
pytest -q
```

### 4) Chạy baseline

```bash
python -m multi_agent_research_lab.cli baseline --query "What is GraphRAG?"
```

### 5) Chạy multi-agent + critic

```bash
python -m multi_agent_research_lab.cli multi-agent --query "Design a production GraphRAG system for a Vietnamese legal assistant, including architecture, evaluation, failure modes, and cost controls." --critic
```

### 6) Chạy benchmark và xuất report

```bash
python -m multi_agent_research_lab.cli benchmark --query "Compare Multi-Agent RAG vs Single-Agent RAG for enterprise incident response with strict SLA." --output benchmark_report.md
```

## Exit ticket

Mỗi nhóm trả lời 2 câu:

1. Case nào nên dùng multi-agent? Vì sao?
2. Case nào không nên dùng multi-agent? Vì sao?
