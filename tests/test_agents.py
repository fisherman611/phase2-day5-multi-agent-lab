from multi_agent_research_lab.agents import SupervisorAgent
from multi_agent_research_lab.core.config import Settings
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow


def test_supervisor_routes_missing_research_first() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    settings = Settings()
    settings.max_iterations = 6
    updated = SupervisorAgent(settings=settings).run(state)
    assert updated.route_history[-1] == "researcher"


def test_supervisor_stops_after_max_iterations() -> None:
    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"), iteration=2)
    settings = Settings()
    settings.max_iterations = 2
    updated = SupervisorAgent(settings=settings).run(state)
    assert updated.route_history[-1] == "done"


def test_workflow_runs_to_final_answer_without_provider() -> None:
    settings = Settings()
    settings.max_iterations = 6
    workflow = MultiAgentWorkflow(settings=settings)
    state = ResearchState(request=ResearchQuery(query="Compare GraphRAG and vanilla RAG"))
    result = workflow.run(state)
    assert result.final_answer is not None
    assert "done" in result.route_history
