"""Benchmark skeleton for single-agent vs multi-agent."""

import re
from time import perf_counter
from typing import Callable

from multi_agent_research_lab.core.schemas import BenchmarkMetrics
from multi_agent_research_lab.core.state import ResearchState


Runner = Callable[[str], ResearchState]


def run_benchmark(
    run_name: str,
    query: str,
    runner: Runner,
) -> tuple[ResearchState, BenchmarkMetrics]:
    """Measure latency and compute lightweight quality/cost proxies."""

    started = perf_counter()
    state = runner(query)
    latency = perf_counter() - started
    metrics = BenchmarkMetrics(
        run_name=run_name,
        latency_seconds=latency,
        estimated_cost_usd=_estimate_cost_usd(state),
        quality_score=_heuristic_quality_score(state),
        citation_coverage=_citation_coverage(state),
        failure_rate=1.0 if state.errors else 0.0,
        notes=_build_notes(state),
    )
    return state, metrics


def _estimate_cost_usd(state: ResearchState) -> float:
    input_tokens = 0
    output_tokens = 0
    for result in state.agent_results:
        raw_input = result.metadata.get("input_tokens")
        raw_output = result.metadata.get("output_tokens")
        if isinstance(raw_input, int):
            input_tokens += raw_input
        if isinstance(raw_output, int):
            output_tokens += raw_output

    # Rough placeholder rates for educational benchmarking only.
    input_rate_per_1m = 0.20
    output_rate_per_1m = 0.60
    return (input_tokens / 1_000_000 * input_rate_per_1m) + (
        output_tokens / 1_000_000 * output_rate_per_1m
    )


def _heuristic_quality_score(state: ResearchState) -> float:
    score = 0.0
    if state.final_answer:
        score += 3.0
    if state.research_notes:
        score += 2.0
    if state.analysis_notes:
        score += 2.0
    if state.sources:
        score += 2.0
    if not state.errors:
        score += 1.0

    answer = state.final_answer or ""
    if re.search(r"\[\d+\]", answer):
        score += 0.5
    return min(score, 10.0)


def _citation_coverage(state: ResearchState) -> float | None:
    answer = state.final_answer
    if not answer:
        return None
    if not state.sources:
        return 0.0
    markers = re.findall(r"\[(\d+)\]", answer)
    if not markers:
        return 0.0
    unique_refs = {int(marker) for marker in markers if marker.isdigit()}
    max_sources = len(state.sources)
    covered = len({ref for ref in unique_refs if 1 <= ref <= max_sources})
    return min(covered / max_sources, 1.0)


def _build_notes(state: ResearchState) -> str:
    fragments = [
        f"sources={len(state.sources)}",
        f"routes={len(state.route_history)}",
        f"errors={len(state.errors)}",
    ]
    return ", ".join(fragments)
