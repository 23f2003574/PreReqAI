from ..models import LLMRequest, LLMResponse
from ..provider import LLMProvider

try:
    import google.generativeai as genai
except ImportError:
    genai = None

SUPPORTED_MODELS = [
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]


class GeminiProvider(LLMProvider):
    """Adapter over the Google Gemini generative AI API."""

    def __init__(self, api_key: str = None, client=None):
        if client is not None:
            self._client = client
            return

        if genai is None:
            raise ImportError(
                "The 'google-generativeai' package is required to use "
                "GeminiProvider. Install it with `pip install google-generativeai`."
            )
        genai.configure(api_key=api_key)
        self._client = genai

    def models(self) -> list:
        return list(SUPPORTED_MODELS)

    def _to_gemini_contents(self, messages):
        return [
            {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [message["content"]],
            }
            for message in messages
        ]

    def complete(self, request: LLMRequest) -> LLMResponse:
        self._check_model_supported(request)

        model = self._client.GenerativeModel(request.model)
        raw = model.generate_content(
            self._to_gemini_contents(request.messages),
            generation_config={
                "temperature": request.temperature,
                "max_output_tokens": request.max_tokens,
            },
        )
        candidate = raw.candidates[0]

        return LLMResponse(
            content=raw.text,
            model=request.model,
            usage={
                "prompt_tokens": raw.usage_metadata.prompt_token_count,
                "completion_tokens": raw.usage_metadata.candidates_token_count,
                "total_tokens": raw.usage_metadata.total_token_count,
            },
            finish_reason=str(candidate.finish_reason),
        )

    def stream(self, request: LLMRequest):
        self._check_model_supported(request)

        model = self._client.GenerativeModel(request.model)
        raw_stream = model.generate_content(
            self._to_gemini_contents(request.messages),
            generation_config={
                "temperature": request.temperature,
                "max_output_tokens": request.max_tokens,
            },
            stream=True,
        )
        for chunk in raw_stream:
            if chunk.text:
                yield chunk.text
