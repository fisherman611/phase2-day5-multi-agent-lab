"""Tracing hooks.

This file intentionally avoids binding to one provider. Students can plug in LangSmith,
Langfuse, OpenTelemetry, or simple JSON traces.
"""

from contextvars import ContextVar, Token
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
import logging
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from multi_agent_research_lab.core.config import get_settings

_CURRENT_LANGSMITH_RUN_ID: ContextVar[UUID | None] = ContextVar(
    "current_langsmith_run_id",
    default=None,
)
logger = logging.getLogger(__name__)


def _get_langsmith_client() -> Any | None:
    settings = get_settings()
    if not settings.langsmith_tracing or not settings.langsmith_api_key:
        return None
    try:
        from langsmith import Client
    except ImportError:
        logger.warning("LangSmith tracing enabled but `langsmith` package is not installed.")
        return None
    return Client(
        api_key=settings.langsmith_api_key,
        api_url=settings.langsmith_endpoint,
    )


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Minimal in-process span context suitable for local tracing."""

    started = perf_counter()
    start_time = datetime.now(UTC)
    span: dict[str, Any] = {
        "name": name,
        "attributes": attributes or {},
        "status": "ok",
        "started_at": start_time.isoformat(),
        "duration_seconds": None,
        "error": None,
    }
    settings = get_settings()
    client = _get_langsmith_client()
    run_id: UUID | None = None
    run_token: Token[UUID | None] | None = None
    if client is not None:
        run_id = uuid4()
        parent_run_id = _CURRENT_LANGSMITH_RUN_ID.get()
        create_kwargs: dict[str, Any] = {
            "id": run_id,
            "start_time": start_time,
            "extra": {"metadata": {"source": "multi_agent_research_lab", **span["attributes"]}},
            "tags": ["multi-agent-research-lab"],
        }
        if parent_run_id is not None:
            create_kwargs["parent_run_id"] = parent_run_id
        try:
            client.create_run(
                name=name,
                inputs={"attributes": span["attributes"]},
                run_type="chain",
                project_name=settings.langsmith_project,
                **create_kwargs,
            )
            run_token = _CURRENT_LANGSMITH_RUN_ID.set(run_id)
        except Exception as exc:
            logger.warning("LangSmith create_run failed for span `%s`: %s", name, exc)
            client = None
            run_id = None

    try:
        yield span
    except Exception as exc:
        span["status"] = "error"
        span["error"] = str(exc)
        raise
    finally:
        span["duration_seconds"] = perf_counter() - started
        end_time = datetime.now(UTC)
        span["ended_at"] = end_time.isoformat()
        if client is not None and run_id is not None:
            outputs = {
                "status": span["status"],
                "duration_seconds": span["duration_seconds"],
                "error": span["error"],
            }
            try:
                client.update_run(
                    run_id,
                    end_time=end_time,
                    error=span["error"],
                    outputs=outputs,
                )
            except Exception as exc:
                logger.warning("LangSmith update_run failed for span `%s`: %s", name, exc)
        if run_token is not None:
            _CURRENT_LANGSMITH_RUN_ID.reset(run_token)
