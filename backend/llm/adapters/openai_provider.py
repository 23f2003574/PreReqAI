from ..models import LLMRequest, LLMResponse
from ..provider import LLMProvider

try:
    import openai
except ImportError:
    openai = None

SUPPORTED_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
]


class OpenAIProvider(LLMProvider):
    """Adapter over the OpenAI chat completions API."""

    def __init__(self, api_key: str = None, client=None):
        if client is not None:
            self._client = client
            return

        if openai is None:
            raise ImportError(
                "The 'openai' package is required to use OpenAIProvider. "
                "Install it with `pip install openai`."
            )
        self._client = openai.OpenAI(api_key=api_key)

    def models(self) -> list:
        return list(SUPPORTED_MODELS)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self._check_model_supported(request)

        raw = self._client.chat.completions.create(
            model=request.model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        choice = raw.choices[0]

        return LLMResponse(
            content=choice.message.content,
            model=raw.model,
            usage={
                "prompt_tokens": raw.usage.prompt_tokens,
                "completion_tokens": raw.usage.completion_tokens,
                "total_tokens": raw.usage.total_tokens,
            },
            finish_reason=choice.finish_reason,
        )

    def stream(self, request: LLMRequest):
        self._check_model_supported(request)

        raw_stream = self._client.chat.completions.create(
            model=request.model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True,
        )
        for chunk in raw_stream:
            delta = chunk.choices[0].delta
            if getattr(delta, "content", None):
                yield delta.content
