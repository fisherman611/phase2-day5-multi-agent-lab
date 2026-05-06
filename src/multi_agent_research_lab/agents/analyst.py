"""Analyst agent skeleton."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.errors import LabError
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient, LLMResponse


class AnalystAgent(BaseAgent):
    """Turns research notes into structured insights."""

    name = "analyst"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.analysis_notes`."""

        research_notes = state.research_notes or "No research notes available."
        with trace_span(
            "agent.analyst",
            {"has_research_notes": bool(state.research_notes)},
        ) as span:
            llm_response: LLMResponse | None = None
            try:
                llm_response = self._llm_client.complete(
                    system_prompt=(
                        "You are an evidence-driven analyst. Convert notes into claims, evidence, "
                        "and risks. Be explicit about uncertainty."
                    ),
                    user_prompt=(
                        f"Query: {state.request.query}\n\n"
                        f"Research Notes:\n{research_notes}\n\n"
                        "Output format:\n"
                        "1) Key Claims\n2) Counterpoints\n3) Weak Evidence / Gaps\n"
                        "4) Recommended Next Validation Steps"
                    ),
                )
                analysis = llm_response.content.strip()
            except LabError as exc:
                state.errors.append(f"analyst_llm_error: {exc}")
                analysis = _fallback_analysis(research_notes)

            state.analysis_notes = analysis
            state.agent_results.append(
                AgentResult(
                    agent=AgentName.ANALYST,
                    content=analysis,
                    metadata={
                        "input_tokens": llm_response.input_tokens if llm_response else None,
                        "output_tokens": llm_response.output_tokens if llm_response else None,
                    },
                )
            )
            span["attributes"]["analysis_length"] = len(analysis)
        state.add_trace_event(
            "agent.analyst.completed",
            {"analysis_length": len(state.analysis_notes or "")},
        )
        return state


def _fallback_analysis(research_notes: str) -> str:
    compact = research_notes.replace("\n", " ").strip()
    short_context = compact[:320]
    return (
        "1) Key Claims:\n"
        f"- Derived from available notes: {short_context}\n\n"
        "2) Counterpoints:\n"
        "- Evidence may be biased toward easily discoverable web sources.\n\n"
        "3) Weak Evidence / Gaps:\n"
        "- Missing quantitative benchmarks and independent replication sources.\n\n"
        "4) Recommended Next Validation Steps:\n"
        "- Verify key claims with at least one additional primary source."
    )
