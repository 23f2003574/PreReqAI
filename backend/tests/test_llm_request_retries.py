import pytest

from backend.llm import LLMProvider, LLMRequest, LLMResponse
from backend.llm.budget import LLMBudgetService
from backend.llm.response_cache import LLMResponseCacheService
from backend.llm.retry import (
    InvalidRetryPolicyError,
    LLMRetryPolicy,
    LLMRetryService,
    PermanentLLMError,
    RetryExhaustedError,
    TransientLLMError,
)


class ScriptedProvider(LLMProvider):
    """A real backend.llm.LLMProvider (Commit #1) that replays a scripted outcome per call."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def models(self):
        return ["test-model"]

    def complete(self, request):
        self.calls += 1
        outcome = self._script[self.calls - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def stream(self, request):
        raise NotImplementedError


def make_request(model="test-model", content="hi"):
    return LLMRequest(model=model, messages=[{"role": "user", "content": content}], temperature=0.0)


def make_response(content="ok"):
    return LLMResponse(
        content=content,
        model="test-model",
        usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        finish_reason="stop",
    )


def test_retry_policy():
    service = LLMRetryService()
    policy = LLMRetryPolicy(policy_id="fast", max_attempts=2, backoff_seconds=0.001)

    configured = service.configure("workspace-1", policy)
    assert configured is policy

    with pytest.raises(InvalidRetryPolicyError):
        service.configure(
            "workspace-2", LLMRetryPolicy(policy_id="bad", max_attempts=0, backoff_seconds=0.001)
        )

    with pytest.raises(InvalidRetryPolicyError):
        service.configure(
            "workspace-3", LLMRetryPolicy(policy_id="bad2", max_attempts=2, backoff_seconds=-1)
        )


def test_transient_failure_retry():
    service = LLMRetryService()
    service.configure(
        "workspace-4", LLMRetryPolicy(policy_id="p", max_attempts=3, backoff_seconds=0.001)
    )

    response = make_response()
    provider = ScriptedProvider([TransientLLMError("timeout"), response])

    result = service.execute(make_request(), "req-1", provider, scope_id="workspace-4")

    assert result is response
    assert provider.calls == 2
    assert service.attempts("req-1") == 2


def test_permanent_failure():
    service = LLMRetryService()
    service.configure(
        "workspace-5", LLMRetryPolicy(policy_id="p", max_attempts=3, backoff_seconds=0.001)
    )

    provider = ScriptedProvider([PermanentLLMError("bad request")])

    with pytest.raises(PermanentLLMError):
        service.execute(make_request(), "req-2", provider, scope_id="workspace-5")

    assert provider.calls == 1
    assert service.attempts("req-2") == 1
    assert service.next_retry("req-2") is None

    # validation failures are never retried and never even reach the provider
    bad_request = LLMRequest(model="test-model", messages=[])
    provider2 = ScriptedProvider([make_response()])

    with pytest.raises(ValueError):
        service.execute(bad_request, "req-2b", provider2, scope_id="workspace-5")

    assert provider2.calls == 0
    assert service.attempts("req-2b") == 0


def test_backoff_calculation():
    policy = LLMRetryPolicy(policy_id="p", max_attempts=5, backoff_seconds=0.5)

    assert LLMRetryService.compute_backoff(policy, 1) == pytest.approx(0.5)
    assert LLMRetryService.compute_backoff(policy, 2) == pytest.approx(1.0)
    assert LLMRetryService.compute_backoff(policy, 3) == pytest.approx(2.0)

    service = LLMRetryService()
    retry_policy = LLMRetryPolicy(policy_id="p2", max_attempts=3, backoff_seconds=0.001)
    service.configure("workspace-6", retry_policy)
    provider = ScriptedProvider(
        [TransientLLMError("x"), TransientLLMError("x"), make_response()]
    )

    service.execute(make_request(), "req-3", provider, scope_id="workspace-6")

    assert service.next_retry("req-3") == pytest.approx(
        LLMRetryService.compute_backoff(retry_policy, 2)
    )


def test_max_attempts():
    service = LLMRetryService()
    service.configure(
        "workspace-7", LLMRetryPolicy(policy_id="p", max_attempts=3, backoff_seconds=0.001)
    )

    provider = ScriptedProvider([TransientLLMError("x")] * 5)

    with pytest.raises(RetryExhaustedError):
        service.execute(make_request(), "req-4", provider, scope_id="workspace-7")

    assert provider.calls == 3
    assert service.attempts("req-4") == 3


def test_success_stopping_retries():
    cache_service = LLMResponseCacheService()
    budget_service = LLMBudgetService()
    budget_service.configure("workspace-8", max_tokens=1000, max_cost=10.0)

    service = LLMRetryService(cache_service=cache_service, budget_service=budget_service)
    service.configure(
        "workspace-8", LLMRetryPolicy(policy_id="p", max_attempts=3, backoff_seconds=0.001)
    )

    response = make_response()
    provider = ScriptedProvider([response, make_response(content="should not be called")])

    result = service.execute(
        make_request(), "req-5", provider, scope_id="workspace-8", budget_scope_id="workspace-8"
    )

    assert result is response
    assert provider.calls == 1

    remaining = budget_service.remaining("workspace-8")
    assert remaining["tokens"] == 1000 - response.usage["total_tokens"]

    # a second execute() for the same request content must not duplicate the call
    result2 = service.execute(
        make_request(), "req-6", provider, scope_id="workspace-8", budget_scope_id="workspace-8"
    )

    assert result2 is response
    assert provider.calls == 1
    assert budget_service.remaining("workspace-8") == remaining
