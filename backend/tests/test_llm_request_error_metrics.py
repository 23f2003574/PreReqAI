from datetime import datetime, timezone

import pytest

from backend.llm.audit import LLMRequestAudit
from backend.llm.budget import BudgetExceededError
from backend.llm.models import LLMRequest
from backend.llm.provider import UnsupportedModelError
from backend.llm.request_errors import (
    LLMRequestErrorService,
    SecretInRequestErrorMetricError,
    UnknownRequestErrorMetricError,
)
from backend.llm.retry import PermanentLLMError, TransientLLMError
from backend.llm.routing import NoEligibleModelError


def make_audit(request_id="req-1", provider="openai", model="gpt-4o"):
    return LLMRequestAudit(
        audit_id=f"audit-{request_id}-1",
        request_id=request_id,
        provider=provider,
        model=model,
        status="failed",
        attempts=1,
        total_tokens=0,
        total_cost=0.0,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_provider_error():
    service = LLMRequestErrorService()

    metric = service.record(make_audit(), UnsupportedModelError("model not supported"))

    assert metric.error_type == "UNSUPPORTED_MODEL"
    assert metric.retryable is False
    assert metric.provider == "openai"
    assert metric.model == "gpt-4o"
    assert service.get("req-1") is metric


def test_validation_error():
    service = LLMRequestErrorService()

    try:
        LLMRequest(model="", messages=[]).validate()
        raised = None
    except ValueError as exc:
        raised = exc

    assert raised is not None
    metric = service.record(make_audit(request_id="req-2"), raised)

    assert metric.error_type == "VALIDATION"
    assert metric.retryable is False


def test_timeout():
    service = LLMRequestErrorService()

    metric = service.record(
        make_audit(request_id="req-3"), TransientLLMError("timed out waiting for response")
    )

    assert metric.error_type == "TRANSIENT"
    assert metric.retryable is True


def test_retryable_classification():
    service = LLMRequestErrorService()

    transient = service.record(make_audit(request_id="req-4"), TransientLLMError("rate limited"))
    permanent = service.record(make_audit(request_id="req-5"), PermanentLLMError("bad request"))
    no_route = service.record(make_audit(request_id="req-6"), NoEligibleModelError("no provider"))
    over_budget = service.record(make_audit(request_id="req-7"), BudgetExceededError("over budget"))

    assert transient.retryable is True
    assert permanent.retryable is False
    assert no_route.retryable is False
    assert over_budget.retryable is False


def test_unknown_error():
    service = LLMRequestErrorService()

    metric = service.record(make_audit(request_id="req-8"), RuntimeError("something unexpected"))

    assert metric.error_type == "UNKNOWN"
    assert metric.retryable is False


def test_provider_model_aggregation():
    service = LLMRequestErrorService()

    service.record(
        make_audit(request_id="req-9", provider="openai", model="gpt-4o"),
        TransientLLMError("timeout"),
    )
    service.record(
        make_audit(request_id="req-10", provider="openai", model="gpt-4o"),
        PermanentLLMError("bad request"),
    )
    service.record(
        make_audit(request_id="req-11", provider="openai", model="gpt-4o-mini"),
        TransientLLMError("timeout"),
    )

    aggregate = service.aggregate("openai", "gpt-4o")
    assert aggregate["count"] == 2
    assert aggregate["retryable_count"] == 1
    assert aggregate["error_type_counts"] == {"TRANSIENT": 1, "PERMANENT": 1}

    empty = service.aggregate("openai", "does-not-exist")
    assert empty == {
        "provider": "openai",
        "model": "does-not-exist",
        "count": 0,
        "retryable_count": 0,
        "error_type_counts": {},
    }

    transient_metrics = service.by_type("TRANSIENT")
    assert {metric.request_id for metric in transient_metrics} == {"req-9", "req-11"}

    with pytest.raises(UnknownRequestErrorMetricError):
        service.get("does-not-exist")


def test_secret_exclusion():
    service = LLMRequestErrorService()
    leaked_audit = make_audit(request_id="req-12", provider="openai sk-liveAbCdEfGhIjKlMnOpQrSt")

    with pytest.raises(SecretInRequestErrorMetricError):
        service.record(leaked_audit, TransientLLMError("timeout"))

    with pytest.raises(UnknownRequestErrorMetricError):
        service.get("req-12")
