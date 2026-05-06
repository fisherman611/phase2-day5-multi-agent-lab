"""Researcher agent skeleton."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.errors import LabError
from multi_agent_research_lab.core.schemas import AgentName, AgentResult, SourceDocument
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.observability.tracing import trace_span
from multi_agent_research_lab.services.llm_client import LLMClient, LLMResponse
from multi_agent_research_lab.services.search_client import SearchClient


class ResearcherAgent(BaseAgent):
    """Collects sources and creates concise research notes."""

    name = "researcher"

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        search_client: SearchClient | None = None,
    ) -> None:
        self._llm_client = llm_client or LLMClient()
        self._search_client = search_client or SearchClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.sources` and `state.research_notes`."""

        with trace_span("agent.researcher", {"query": state.request.query}) as span:
            sources = self._search_client.search(
                query=state.request.query,
                max_results=state.request.max_sources,
            )
            state.sources = sources
            prompt_sources = _format_sources_for_prompt(sources)

            llm_response: LLMResponse | None = None
            try:
                llm_response = self._llm_client.complete(
                    system_prompt=(
                        "You are a research specialist. Extract key facts, keep only high-signal "
                        "content, and include source markers [1], [2], ..."
                        " tied to provided sources."
                    ),
                    user_prompt=(
                        f"Query: {state.request.query}\n\n"
                        "Sources:\n"
                        f"{prompt_sources}\n\n"
                        "Output format:\n"
                        "- 4 to 8 bullet points with evidence.\n"
                        "- Add a final line `Open Questions:` with unknowns."
                    ),
                )
                notes = llm_response.content.strip()
            except LabError as exc:
                state.errors.append(f"researcher_llm_error: {exc}")
                notes = _fallback_notes(state.request.query, sources)

            state.research_notes = notes
            state.agent_results.append(
                AgentResult(
                    agent=AgentName.RESEARCHER,
                    content=notes,
                    metadata={
                        "sources_count": len(sources),
                        "input_tokens": llm_response.input_tokens if llm_response else None,
                        "output_tokens": llm_response.output_tokens if llm_response else None,
                    },
                )
            )
            span["attributes"]["sources_count"] = len(sources)
        state.add_trace_event(
            "agent.researcher.completed",
            {"sources_count": len(state.sources), "notes_length": len(state.research_notes or "")},
        )
        return state


def _format_sources_for_prompt(sources: list[SourceDocument]) -> str:
    if not sources:
        return "- No sources available."
    lines: list[str] = []
    for idx, source in enumerate(sources, start=1):
        source_url = f" ({source.url})" if source.url else ""
        lines.append(f"[{idx}] {source.title}{source_url}\n{source.snippet}")
    return "\n\n".join(lines)


def _fallback_notes(query: str, sources: list[SourceDocument]) -> str:
    if not sources:
        return (
            f"- Could not retrieve sources for: {query}\n"
            "- Next action: refine query keywords and retry search.\n"
            "Open Questions: Which sub-topic should be prioritized first?"
        )
    bullets: list[str] = []
    for idx, source in enumerate(sources[:5], start=1):
        bullets.append(f"- [{idx}] {source.title}: {source.snippet.strip()}")
    bullets.append("Open Questions: Which claims require independent verification?")
    return "\n".join(bullets)
