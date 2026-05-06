"""LangGraph workflow skeleton."""

from collections.abc import Callable
from typing import TypedDict

from multi_agent_research_lab.agents import (
    AnalystAgent,
    CriticAgent,
    ResearcherAgent,
    SupervisorAgent,
    WriterAgent,
)
from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.state import ResearchState


class _GraphState(TypedDict):
    state: ResearchState


class MultiAgentWorkflow:
    """Builds and runs the multi-agent graph."""

    def __init__(
        self,
        settings: Settings | None = None,
        include_critic: bool = False,
    ) -> None:
        self._settings = settings or get_settings()
        self._include_critic = include_critic
        self._supervisor = SupervisorAgent(settings=self._settings, include_critic=include_critic)
        self._researcher = ResearcherAgent()
        self._analyst = AnalystAgent()
        self._writer = WriterAgent()
        self._critic = CriticAgent()
        self._worker_map: dict[str, Callable[[ResearchState], ResearchState]] = {
            "researcher": self._researcher.run,
            "analyst": self._analyst.run,
            "writer": self._writer.run,
            "critic": self._critic.run,
        }

    def build(self) -> object:
        """Create a LangGraph graph when available, otherwise return fallback metadata."""

        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError:
            return {
                "engine": "fallback_loop",
                "nodes": ["supervisor", "researcher", "analyst", "writer"]
                + (["critic"] if self._include_critic else []),
            }

        graph = StateGraph(_GraphState)

        def supervisor_node(state: _GraphState) -> dict[str, ResearchState]:
            return {"state": self._supervisor.run(state["state"])}

        def researcher_node(state: _GraphState) -> dict[str, ResearchState]:
            return {"state": self._researcher.run(state["state"])}

        def analyst_node(state: _GraphState) -> dict[str, ResearchState]:
            return {"state": self._analyst.run(state["state"])}

        def writer_node(state: _GraphState) -> dict[str, ResearchState]:
            return {"state": self._writer.run(state["state"])}

        def critic_node(state: _GraphState) -> dict[str, ResearchState]:
            return {"state": self._critic.run(state["state"])}

        def route(state: _GraphState) -> str:
            return state["state"].route_history[-1]

        graph.add_node("supervisor", supervisor_node)
        graph.add_node("researcher", researcher_node)
        graph.add_node("analyst", analyst_node)
        graph.add_node("writer", writer_node)
        if self._include_critic:
            graph.add_node("critic", critic_node)

        route_map: dict[str, str] = {
            "researcher": "researcher",
            "analyst": "analyst",
            "writer": "writer",
            "done": END,
        }
        if self._include_critic:
            route_map["critic"] = "critic"

        graph.add_edge(START, "supervisor")
        graph.add_conditional_edges("supervisor", route, route_map)
        graph.add_edge("researcher", "supervisor")
        graph.add_edge("analyst", "supervisor")
        graph.add_edge("writer", "supervisor")
        if self._include_critic:
            graph.add_edge("critic", "supervisor")

        return graph.compile()

    def run(self, state: ResearchState) -> ResearchState:
        """Execute the workflow and return final state."""

        graph = self.build()
        if hasattr(graph, "invoke"):
            result: object = graph.invoke({"state": state})
            if isinstance(result, dict):
                output_state = result.get("state")
                if isinstance(output_state, ResearchState):
                    return output_state
            state.errors.append("Graph invoke returned unexpected output; used loop fallback.")
        return self._run_loop(state)

    def _run_loop(self, state: ResearchState) -> ResearchState:
        while state.iteration < self._settings.max_iterations:
            state = self._supervisor.run(state)
            route = state.route_history[-1] if state.route_history else "done"
            if route == "done":
                break
            worker = self._worker_map.get(route)
            if worker is None:
                state.errors.append(f"Unknown route: {route}")
                break
            try:
                state = worker(state)
            except Exception as exc:  # pragma: no cover - defensive path
                state.errors.append(f"{route}_execution_error: {exc}")
                if route != "writer" and not state.final_answer:
                    state.record_route("writer")
                    state = self._writer.run(state)
                    state.record_route("done")
                else:
                    state.record_route("done")
                break

        if not state.final_answer and state.sources:
            state = self._writer.run(state)
            state.record_route("done")
        return state
