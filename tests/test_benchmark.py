from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import run_benchmark


def test_benchmark_computes_metrics() -> None:
    def runner(_: str) -> ResearchState:
        state = ResearchState(request=ResearchQuery(query="What is multi-agent orchestration?"))
        state.final_answer = "Answer with citation [1]."
        state.sources = []
        return state

    _, metrics = run_benchmark("baseline", "What is multi-agent orchestration?", runner)
    assert metrics.latency_seconds >= 0
    assert metrics.quality_score is not None
    assert metrics.failure_rate == 0.0
