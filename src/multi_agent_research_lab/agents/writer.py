"""Writer agent skeleton."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.errors import LabError
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient, LLMResponse


class WriterAgent(BaseAgent):
    """Produces final answer from research and analysis notes."""

    name = "writer"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.final_answer`."""

        research_notes = state.research_notes or "No research notes available."
        analysis_notes = state.analysis_notes or "No analysis notes available."
        with trace_span(
            "agent.writer",
            {
                "audience": state.request.audience,
                "sources_count": len(state.sources),
            },
        ) as span:
            llm_response: LLMResponse | None = None
            try:
                llm_response = self._llm_client.complete(
                    system_prompt=(
                        "You are a technical writer. Provide clear and balanced answers with "
                        "source markers [1], [2], ... and a concise references section."
                    ),
                    user_prompt=(
                        f"Audience: {state.request.audience}\n"
                        f"Query: {state.request.query}\n\n"
                        f"Research Notes:\n{research_notes}\n\n"
                        f"Analysis Notes:\n{analysis_notes}\n\n"
                        "Output format:\n"
                        "- Executive Summary\n"
                        "- Detailed Answer\n"
                        "- Risks and Unknowns\n"
                        "- References (use [n] markers that map to source list)"
                    ),
                )
                answer = llm_response.content.strip()
            except LabError as exc:
                state.errors.append(f"writer_llm_error: {exc}")
                answer = _fallback_answer(state)

            state.final_answer = answer
            state.agent_results.append(
                AgentResult(
                    agent=AgentName.WRITER,
                    content=answer,
                    metadata={
                        "input_tokens": llm_response.input_tokens if llm_response else None,
                        "output_tokens": llm_response.output_tokens if llm_response else None,
                    },
                )
            )
            span["attributes"]["answer_length"] = len(answer)
        state.add_trace_event(
            "agent.writer.completed",
            {"answer_length": len(state.final_answer or "")},
        )
        return state


def _fallback_answer(state: ResearchState) -> str:
    lines = [
        "Executive Summary",
        f"- Query: {state.request.query}",
        "- This answer was generated from available notes with limited model assistance.",
        "",
        "Detailed Answer",
        f"{state.analysis_notes or state.research_notes or 'No evidence collected.'}",
        "",
        "Risks and Unknowns",
        "- Some claims may require stronger primary-source validation.",
        "",
        "References",
    ]
    if state.sources:
        for idx, source in enumerate(state.sources[:5], start=1):
            ref_url = f" - {source.url}" if source.url else ""
            lines.append(f"[{idx}] {source.title}{ref_url}")
    else:
        lines.append("- No sources captured.")
    return "\n".join(lines)
