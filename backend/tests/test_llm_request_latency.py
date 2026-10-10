from datetime import datetime, timedelta, timezone

import pytest

from backend.llm.audit import LLMRequestAudit, LLMRequestAuditService
from backend.llm.models import LLMRequest
from backend.llm.request_latency import (
    IncompleteRequestError,
    LLMRequestLatencyService,
    SecretInRequestLatencyError,
    UnknownRequestLatencyError,
)
from backend.llm.usage import LLMUsageService


def make_request(model="gpt-4o"):
    return LLMRequest(model=model, messages=[{"role": "user", "content": "hello"}])


def build_env():
    audit_service = LLMRequestAuditService(LLMUsageService())
    latency_service = LLMRequestLatencyService()
    return audit_service, latency_service


def test_successful_request():
    audit_service, latency_service = build_env()
    audit_service.start(make_request(), "req-1", "openai")
    completed = audit_service.complete("req-1", status="succeeded")

    latency = latency_service.record(completed)

    assert latency.request_id == "req-1"
    assert latency.provider == "openai"
    assert latency.model == "gpt-4o"
    assert latency.status == "succeeded"
    assert latency.duration >= 0
    assert latency_service.get("req-1") is latency


def test_failed_request():
    audit_service, latency_service = build_env()
    audit_service.start(make_request(), "req-2", "openai")
    completed = audit_service.complete("req-2", status="failed")

    latency = latency_service.record(completed)

    assert latency.status == "failed"
    assert latency.request_id == "req-2"


def test_timeout():
    audit_service, latency_service = build_env()
    audit_service.start(make_request(), "req-3", "openai")
    completed = audit_service.complete("req-3", status="timed_out")

    latency = latency_service.record(completed)

    assert latency.status == "timed_out"


def test_duration_calculation():
    _, latency_service = build_env()
    created_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    completed_at = created_at + timedelta(seconds=2, milliseconds=500)

    audit = _make_audit(
        request_id="req-4",
        provider="openai",
        model="gpt-4o",
        status="succeeded",
        created_at=created_at,
        completed_at=completed_at,
    )

    latency = latency_service.record(audit)

    assert latency.duration == 2.5


def test_provider_model_aggregation():
    _, latency_service = build_env()

    fast = _make_audit(
        "req-6", "openai", "gpt-4o", "succeeded",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=1),
    )
    slow = _make_audit(
        "req-7", "openai", "gpt-4o", "failed",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=3),
    )
    other_model = _make_audit(
        "req-8", "openai", "gpt-4o-mini", "succeeded",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=10),
    )
    latency_service.record(fast)
    latency_service.record(slow)
    latency_service.record(other_model)

    aggregate = latency_service.aggregate("openai", "gpt-4o")
    assert aggregate["count"] == 2
    assert aggregate["average_duration"] == 2.0
    assert aggregate["status_counts"] == {"succeeded": 1, "failed": 1}

    empty = latency_service.aggregate("openai", "does-not-exist")
    assert empty["count"] == 0
    assert empty["average_duration"] is None
    assert empty["status_counts"] == {}


def test_missing_request():
    audit_service, latency_service = build_env()

    with pytest.raises(UnknownRequestLatencyError):
        latency_service.get("does-not-exist")

    audit_service.start(make_request(), "req-9", "openai")
    in_flight = audit_service.get("req-9")
    assert in_flight.completed_at is None

    with pytest.raises(IncompleteRequestError):
        latency_service.record(in_flight)


def test_secret_exclusion():
    _, latency_service = build_env()
    leaked = _make_audit(
        "req-10",
        "openai sk-liveAbCdEfGhIjKlMnOpQrSt",
        "gpt-4o",
        "succeeded",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=1),
    )

    with pytest.raises(SecretInRequestLatencyError):
        latency_service.record(leaked)

    with pytest.raises(UnknownRequestLatencyError):
        latency_service.get("req-10")


def _make_audit(request_id, provider, model, status, created_at, completed_at):
    return LLMRequestAudit(
        audit_id=f"audit-{request_id}-1",
        request_id=request_id,
        provider=provider,
        model=model,
        status=status,
        attempts=1,
        total_tokens=0,
        total_cost=0.0,
        created_at=created_at,
        completed_at=completed_at,
    )
