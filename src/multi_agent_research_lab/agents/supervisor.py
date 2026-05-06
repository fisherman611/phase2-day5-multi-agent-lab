"""Supervisor / router skeleton."""

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.state import ResearchState


class SupervisorAgent(BaseAgent):
    """Decides which worker should run next and when to stop."""

    name = "supervisor"

    def __init__(self, settings: Settings | None = None, include_critic: bool = False) -> None:
        self._settings = settings or get_settings()
        self._include_critic = include_critic

    def run(self, state: ResearchState) -> ResearchState:
        """Choose the next step and store it in `state.route_history`."""

        if state.iteration >= self._settings.max_iterations:
            route = "done"
            reason = "max_iterations_reached"
        elif state.errors and len(state.errors) >= 2 and not state.final_answer:
            route = "writer"
            reason = "fallback_after_errors"
        elif not state.sources or not state.research_notes:
            route = "researcher"
            reason = "missing_research"
        elif not state.analysis_notes:
            route = "analyst"
            reason = "missing_analysis"
        elif not state.final_answer:
            route = "writer"
            reason = "missing_final_answer"
        elif self._include_critic and not self._critic_has_run(state):
            route = "critic"
            reason = "post_write_quality_check"
        else:
            route = "done"
            reason = "workflow_complete"

        state.record_route(route)
        state.add_trace_event(
            "supervisor.route_decision",
            {
                "route": route,
                "reason": reason,
                "iteration": state.iteration,
                "errors": len(state.errors),
            },
        )
        return state

    @staticmethod
    def _critic_has_run(state: ResearchState) -> bool:
        return any(result.agent.value == "critic" for result in state.agent_results)
