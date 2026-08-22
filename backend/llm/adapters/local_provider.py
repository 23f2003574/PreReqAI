import requests

from ..models import LLMRequest, LLMResponse
from ..provider import LLMProvider, UnsupportedOperationError

DEFAULT_MODELS = [
    "llama3",
    "mistral",
]


class LocalLLMProvider(LLMProvider):
    """Adapter over a locally hosted LLM server (e.g. Ollama)."""

    def __init__(self, base_url="http://localhost:11434", available_models=None, session=None):
        self._base_url = base_url.rstrip("/")
        self._available_models = (
            list(available_models) if available_models else list(DEFAULT_MODELS)
        )
        self._session = session or requests.Session()

    def models(self) -> list:
        return list(self._available_models)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self._check_model_supported(request)

        response = self._session.post(
            f"{self._base_url}/api/chat",
            json={
                "model": request.model,
                "messages": request.messages,
                "options": {"temperature": request.temperature},
                "stream": False,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        return LLMResponse(
            content=data["message"]["content"],
            model=request.model,
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            finish_reason=data.get("done_reason", "stop"),
        )

    def stream(self, request: LLMRequest):
        raise UnsupportedOperationError(
            "LocalLLMProvider does not support streaming responses"
        )
