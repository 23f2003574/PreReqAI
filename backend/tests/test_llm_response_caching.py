from backend.llm import LLMRequest, LLMResponse
from backend.llm.response_cache import LLMResponseCacheService
from backend.llm.context import LLMContextItem, LLMContextService


def build_request(model="gpt-4o", **overrides):
    fields = {
        "model": model,
        "messages": [{"role": "user", "content": "What is 2+2?"}],
        "temperature": 0.0,
    }
    fields.update(overrides)
    return LLMRequest(**fields)


def build_response(content="4", model="gpt-4o", finish_reason="stop"):
    return LLMResponse(
        content=content,
        model=model,
        usage={"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        finish_reason=finish_reason,
    )


def test_cache_hit_and_miss():
    service = LLMResponseCacheService()
    request = build_request()

    assert service.get(request) is None

    response = build_response()
    service.set(request, response)

    assert service.get(request) is response

    different_request = build_request(messages=[{"role": "user", "content": "different"}])
    assert service.get(different_request) is None

    # reuse Commit #4's context layer to build the request that gets cached
    context_service = LLMContextService()
    context_service.create("req-ctx-1", system="Be terse.")
    context_service.add(
        "req-ctx-1", LLMContextItem(type="user", content="Summarize gradient descent.", priority=1)
    )
    built = context_service.build("req-ctx-1")
    context_request = LLMRequest(model="gpt-4o", messages=built["messages"], temperature=0.0)

    assert service.get(context_request) is None
    service.set(context_request, build_response())
    assert service.get(context_request) is not None


def test_deterministic_key():
    service = LLMResponseCacheService()
    request_a = build_request()
    request_b = build_request()

    entry = service.set(request_a, build_response())

    assert entry.cache_key == service.compute_key(request_b)
    assert entry.request_hash == service._request_hash(request_b)

    other_model_request = build_request(model="gemini-1.5-pro")
    assert service.compute_key(other_model_request) != entry.cache_key


def test_expiry():
    service = LLMResponseCacheService()
    request = build_request()
    response = build_response()

    service.set(request, response, ttl=-1)
    assert service.get(request) is None

    service.set(request, response, ttl=1000)
    assert service.get(request) is response

    service.set(request, response)
    assert service.get(request) is response


def test_invalidation():
    service = LLMResponseCacheService()
    request = build_request()
    service.set(request, build_response())

    assert service.get(request) is not None
    assert service.invalidate(request) is True
    assert service.get(request) is None
    assert service.invalidate(request) is False


def test_model_isolation():
    service = LLMResponseCacheService()
    request_a = build_request(model="gpt-4o")
    request_b = build_request(model="gemini-1.5-pro")

    service.set(request_a, build_response(model="gpt-4o"))
    service.set(request_b, build_response(model="gemini-1.5-pro"))

    assert service.get(request_a) is not None
    assert service.get(request_b) is not None

    removed = service.clear(scope_id="gpt-4o")
    assert removed == 1
    assert service.get(request_a) is None
    assert service.get(request_b) is not None

    cleared_all = service.clear()
    assert cleared_all == 1
    assert service.get(request_b) is None


def test_non_cacheable_request():
    service = LLMResponseCacheService()
    request = build_request()

    entry = service.set(request, build_response(), cacheable=False)
    assert entry is None
    assert service.get(request) is None

    failed_response = build_response(content="", finish_reason="error")
    entry2 = service.set(request, failed_response)
    assert entry2 is None
    assert service.get(request) is None
