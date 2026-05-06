"""Command-line entrypoint for the lab starter."""

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.errors import LabError
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import run_benchmark
from multi_agent_research_lab.evaluation.report import render_markdown_report
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.storage import LocalArtifactStore

app = typer.Typer(help="Multi-Agent Research Lab starter CLI")
console = Console()


def _init() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)


@app.command()
def baseline(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run a single-agent baseline using the configured LLM provider."""

    _init()
    request = ResearchQuery(query=query)
    state = ResearchState(request=request)
    try:
        llm_client = LLMClient()
        completion = llm_client.complete(
            system_prompt=(
                "You are a concise research assistant. Provide a factual answer, include caveats, "
                "and end with a short 'What to verify next' list."
            ),
            user_prompt=request.query,
        )
        state.final_answer = completion.content
    except LabError as exc:
        state.final_answer = f"Baseline failed to call provider: {exc}"
    console.print(Panel.fit(state.final_answer, title="Single-Agent Baseline"))


@app.command("multi-agent")
def multi_agent(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
    include_critic: Annotated[bool, typer.Option("--critic/--no-critic")] = False,
) -> None:
    """Run the multi-agent workflow."""

    _init()
    state = ResearchState(request=ResearchQuery(query=query))
    workflow = MultiAgentWorkflow(include_critic=include_critic)
    result = workflow.run(state)
    console.print(result.model_dump_json(indent=2))


@app.command("benchmark")
def benchmark(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output markdown path"),
    ] = "benchmark_report.md",
) -> None:
    """Run baseline and multi-agent benchmarks, then save a markdown report."""

    _init()

    def baseline_runner(q: str) -> ResearchState:
        request = ResearchQuery(query=q)
        state = ResearchState(request=request)
        try:
            llm_client = LLMClient()
            completion = llm_client.complete(
                system_prompt="You are a helpful research assistant.",
                user_prompt=q,
            )
            state.final_answer = completion.content
        except LabError as exc:
            state.errors.append(f"baseline_llm_error: {exc}")
            state.final_answer = "Baseline fallback answer due to provider configuration issue."
        return state

    def multi_runner(q: str) -> ResearchState:
        state = ResearchState(request=ResearchQuery(query=q))
        return MultiAgentWorkflow().run(state)

    _, baseline_metrics = run_benchmark("baseline", query, baseline_runner)
    _, multi_metrics = run_benchmark("multi_agent", query, multi_runner)
    report = render_markdown_report([baseline_metrics, multi_metrics])
    path = LocalArtifactStore().write_text(output, report)
    console.print(Panel.fit(f"Saved benchmark report to {path}", title="Benchmark Complete"))


if __name__ == "__main__":
    app()
