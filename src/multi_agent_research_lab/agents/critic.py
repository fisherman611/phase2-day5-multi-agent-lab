"""Optional critic agent skeleton for bonus work."""

import re

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState


class CriticAgent(BaseAgent):
    """Optional fact-checking and safety-review agent."""

    name = "critic"

    def run(self, state: ResearchState) -> ResearchState:
        """Validate final answer and append findings."""

        answer = state.final_answer or ""
        citations = re.findall(r"\[\d+\]", answer)
        findings: list[str] = []

        if not answer.strip():
            findings.append("Final answer is empty.")
        if state.sources and not citations:
            findings.append("No citation markers found despite having sources.")
        if len(answer) < 200:
            findings.append("Answer is very short; may lack depth.")
        if not findings:
            findings.append("No critical issues detected by heuristic critic.")

        critique = "\n".join(f"- {item}" for item in findings)
        state.agent_results.append(
            AgentResult(
                agent=AgentName.CRITIC,
                content=critique,
                metadata={
                    "findings_count": len(findings),
                    "citation_markers": len(citations),
                },
            )
        )
        state.add_trace_event(
            "agent.critic.completed",
            {"findings_count": len(findings), "citation_markers": len(citations)},
        )
        return state
