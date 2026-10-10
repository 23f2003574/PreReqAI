from types import SimpleNamespace

import pytest

from backend.llm import (
    LLMRequest,
    LLMResponse,
    UnsupportedModelError,
    UnsupportedOperationError,
    get_provider,
)
from backend.llm.adapters import GeminiProvider, LocalLLMProvider, OpenAIProvider


class FakeOpenAIClient:
    """Stands in for the `openai` SDK client so tests need no real dependency."""

    def __init__(self, stream_chunks=None):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._stream_chunks = stream_chunks or ["Hel", "lo"]

    def _create(self, model, messages, temperature, max_tokens, stream=False):
        if stream:
            return (
                SimpleNamespace(
                    choices=[SimpleNamespace(delta=SimpleNamespace(content=chunk))]
                )
                for chunk in self._stream_chunks
            )
        return SimpleNamespace(
            model=model,
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Hello there"),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=10, completion_tokens=5, total_tokens=15
            ),
        )


class FakeGeminiModel:
    def __init__(self, model_name):
        self.model_name = model_name

    def generate_content(self, contents, generation_config, stream=False):
        if stream:
            return (SimpleNamespace(text=chunk) for chunk in ["Bon", "jour"])
        return SimpleNamespace(
            text="Bonjour",
            candidates=[SimpleNamespace(finish_reason="STOP")],
            usage_metadata=SimpleNamespace(
                prompt_token_count=8,
                candidates_token_count=4,
                total_token_count=12,
            ),
        )


class FakeGeminiClient:
    def GenerativeModel(self, model_name):
        return FakeGeminiModel(model_name)


class FakeLocalSession:
    def __init__(self, payload=None):
        self._payload = payload or {
            "message": {"content": "local reply"},
            "prompt_eval_count": 3,
            "eval_count": 2,
            "done_reason": "stop",
        }
        self.last_request = None

    def post(self, url, json, timeout):
        self.last_request = {"url": url, "json": json, "timeout": timeout}
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: self._payload,
        )


def make_request(model="gpt-4o", **overrides):
    fields = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
    }
    fields.update(overrides)
    return LLMRequest(**fields)


def test_request_validation():
    make_request().validate()

    with pytest.raises(ValueError):
        LLMRequest(model="", messages=[{"role": "user", "content": "hi"}]).validate()

    with pytest.raises(ValueError):
        LLMRequest(model="gpt-4o", messages=[]).validate()

    with pytest.raises(ValueError):
        LLMRequest(model="gpt-4o", messages=[{"role": "user"}]).validate()

    with pytest.raises(ValueError):
        make_request(temperature=5.0).validate()

    with pytest.raises(ValueError):
        make_request(max_tokens=0).validate()


def test_provider_selection():
    assert isinstance(get_provider("local"), LocalLLMProvider)
    assert isinstance(
        get_provider("openai", client=FakeOpenAIClient()), OpenAIProvider
    )
    assert isinstance(
        get_provider("gemini", client=FakeGeminiClient()), GeminiProvider
    )

    with pytest.raises(ValueError):
        get_provider("does-not-exist")


def test_normalized_response():
    openai_provider = OpenAIProvider(client=FakeOpenAIClient())
    openai_response = openai_provider.complete(make_request(model="gpt-4o"))

    gemini_provider = GeminiProvider(client=FakeGeminiClient())
    gemini_response = gemini_provider.complete(make_request(model="gemini-1.5-pro"))

    for response in (openai_response, gemini_response):
        assert isinstance(response, LLMResponse)
        assert isinstance(response.content, str) and response.content
        assert isinstance(response.usage, dict)
        assert {"prompt_tokens", "completion_tokens", "total_tokens"} <= set(
            response.usage
        )
        assert isinstance(response.finish_reason, str)

    assert openai_response.content == "Hello there"
    assert gemini_response.content == "Bonjour"


def test_unsupported_model():
    provider = OpenAIProvider(client=FakeOpenAIClient())

    with pytest.raises(UnsupportedModelError):
        provider.complete(make_request(model="not-a-real-model"))


def test_streaming_interface():
    provider = OpenAIProvider(client=FakeOpenAIClient(stream_chunks=["a", "b", "c"]))

    chunks = list(provider.stream(make_request(model="gpt-4o")))
    assert chunks == ["a", "b", "c"]

    local_provider = LocalLLMProvider(session=FakeLocalSession())
    with pytest.raises(UnsupportedOperationError):
        list(local_provider.stream(make_request(model="llama3")))


def test_provider_isolation():
    import backend.llm  # noqa: F401 -- must import cleanly with no SDKs installed
    from backend.llm.adapters import openai_provider, gemini_provider

    with pytest.raises(ImportError):
        OpenAIProvider(api_key="sk-test")

    session = FakeLocalSession()
    local_provider = LocalLLMProvider(
        base_url="http://localhost:11434", session=session
    )
    local_provider.complete(make_request(model="llama3"))

    assert "gpt" not in str(session.last_request).lower()
    assert openai_provider.openai is None
    assert gemini_provider.genai is None
