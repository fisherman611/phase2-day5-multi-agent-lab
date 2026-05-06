"""LLM client abstraction.

Production note: agents should depend on this interface instead of importing an SDK directly.
"""

from dataclasses import dataclass

from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.errors import LabError


def _as_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


@dataclass(frozen=True)
class LLMResponse:
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


class LLMClient:
    """NVIDIA-backed LLM client."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Return a model completion from NVIDIA AI Endpoints."""

        if not self._settings.nvidia_api_key:
            raise LabError("Missing NVIDIA_API_KEY in environment.")

        try:
            from langchain_nvidia_ai_endpoints import ChatNVIDIA
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise LabError(
                "Missing dependency `langchain-nvidia-ai-endpoints`. "
                "Install with: pip install -e \".[llm]\""
            ) from exc

        client = ChatNVIDIA(
            model=self._settings.nvidia_model,
            api_key=self._settings.nvidia_api_key,
            base_url=self._settings.nvidia_base_url,
            temperature=0.2,
            top_p=0.7,
            max_tokens=1024,
        )
        response = client.invoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )

        usage = getattr(response, "usage_metadata", None)
        input_tokens = _as_int(usage.get("input_tokens")) if isinstance(usage, dict) else None
        output_tokens = _as_int(usage.get("output_tokens")) if isinstance(usage, dict) else None
        content = str(getattr(response, "content", ""))

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
