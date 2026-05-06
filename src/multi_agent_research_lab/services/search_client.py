"""Search client abstraction for ResearcherAgent."""

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.schemas import SourceDocument

logger = logging.getLogger(__name__)


class SearchClient:
    """Provider-agnostic search client with Tavily and local fallback."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search for documents relevant to a query."""

        clipped_results = max(1, min(max_results, 20))
        if self._settings.tavily_api_key:
            documents = self._search_tavily(query=query, max_results=clipped_results)
            if documents:
                return documents
            logger.warning("Falling back to local mock search results for query: %s", query)
        return self._search_mock(query=query, max_results=clipped_results)

    def _search_tavily(self, query: str, max_results: int) -> list[SourceDocument]:
        payload = {
            "api_key": self._settings.tavily_api_key,
            "query": query,
            "max_results": max_results,
            "include_answer": False,
            "search_depth": "basic",
        }
        request = Request(
            url="https://api.tavily.com/search",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._settings.timeout_seconds) as response:
                raw_response = response.read().decode("utf-8")
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            logger.warning("Tavily search failed: %s", exc)
            return []

        try:
            parsed: object = json.loads(raw_response)
        except json.JSONDecodeError:
            return []

        if not isinstance(parsed, dict):
            return []
        raw_results = parsed.get("results")
        if not isinstance(raw_results, list):
            return []

        documents: list[SourceDocument] = []
        for item in raw_results[:max_results]:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            url = item.get("url")
            snippet = item.get("content")
            if not isinstance(title, str) or not isinstance(snippet, str):
                continue
            normalized_url = url if isinstance(url, str) and url else None
            documents.append(
                SourceDocument(
                    title=title.strip() or "Untitled source",
                    url=normalized_url,
                    snippet=snippet.strip(),
                    metadata={"provider": "tavily"},
                )
            )
        return documents

    def _search_mock(self, query: str, max_results: int) -> list[SourceDocument]:
        base_docs: list[tuple[str, str, str]] = [
            (
                "Anthropic Engineering - Building Effective Agents",
                "https://www.anthropic.com/engineering/building-effective-agents",
                "Practical patterns for decomposition, verification, and tool-using agents.",
            ),
            (
                "LangGraph Concepts",
                "https://langchain-ai.github.io/langgraph/concepts/",
                "State-machine style orchestration with explicit nodes, edges, and routing.",
            ),
            (
                "OpenAI Agents Orchestration Guide",
                "https://developers.openai.com/api/docs/guides/agents/orchestration",
                "Handoffs, guardrails, and workflow orchestration patterns for agent systems.",
            ),
            (
                "LangSmith Documentation",
                "https://docs.smith.langchain.com/",
                "Tracing, observability, and evaluation workflows for LLM applications.",
            ),
            (
                "Google SRE Workbook - Monitoring Distributed Systems",
                "https://sre.google/workbook/monitoring/",
                "Reliability patterns for multi-step agent pipelines and failure handling.",
            ),
            (
                "NVIDIA API Catalog",
                "https://build.nvidia.com/",
                "Model catalog and inference endpoint patterns for hosted foundation models.",
            ),
        ]
        seed = sum(ord(char) for char in query)
        docs: list[SourceDocument] = []
        for idx in range(max_results):
            doc = base_docs[(seed + idx) % len(base_docs)]
            docs.append(
                SourceDocument(
                    title=doc[0],
                    url=doc[1],
                    snippet=f"{doc[2]} Query focus: {query[:180]}",
                    metadata={"provider": "mock"},
                )
            )
        return docs
