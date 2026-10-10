from datetime import datetime, timedelta, timezone

from backend.llm.audit import LLMRequestAudit
from backend.llm.provider_reliability import LLMProviderReliabilityService
from backend.llm.request_errors import LLMRequestErrorService
from backend.llm.request_latency import LLMRequestLatencyService
from backend.llm.retry import PermanentLLMError, TransientLLMError


def make_audit(request_id, provider, model, status, duration_seconds=1.0):
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
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
        completed_at=created_at + timedelta(seconds=duration_seconds),
    )


def build_env():
    latency_service = LLMRequestLatencyService()
    error_service = LLMRequestErrorService()
    reliability = LLMProviderReliabilityService(latency_service, error_service)
    return latency_service, error_service, reliability


def test_success_rate():
    latency_service, _, reliability = build_env()
    for i in range(3):
        latency_service.record(make_audit(f"req-{i}", "openai", "gpt-4o", "succeeded"))
    latency_service.record(make_audit("req-fail", "openai", "gpt-4o", "failed"))

    assert reliability.success_rate() == 0.75


def test_failure_rate():
    latency_service, _, reliability = build_env()
    for i in range(3):
        latency_service.record(make_audit(f"req-{i}", "openai", "gpt-4o", "succeeded"))
    latency_service.record(make_audit("req-fail", "openai", "gpt-4o", "failed"))

    assert reliability.failure_rate() == 0.25
    assert reliability.success_rate() + reliability.failure_rate() == 1.0


def test_provider_aggregation():
    latency_service, _, reliability = build_env()
    latency_service.record(make_audit("req-1", "openai", "gpt-4o", "succeeded"))
    latency_service.record(make_audit("req-2", "openai", "gpt-4o", "failed"))
    latency_service.record(make_audit("req-3", "gemini", "gemini-1.5-pro", "succeeded"))
    latency_service.record(make_audit("req-4", "gemini", "gemini-1.5-pro", "succeeded"))

    by_provider = reliability.by_provider()

    assert by_provider["openai"]["count"] == 2
    assert by_provider["openai"]["success_rate"] == 0.5
    assert by_provider["gemini"]["count"] == 2
    assert by_provider["gemini"]["success_rate"] == 1.0


def test_model_aggregation():
    latency_service, _, reliability = build_env()
    latency_service.record(make_audit("req-1", "openai", "gpt-4o", "succeeded"))
    latency_service.record(make_audit("req-2", "openai", "gpt-4o-mini", "failed"))
    latency_service.record(make_audit("req-3", "openai", "gpt-4o-mini", "failed"))

    by_model = reliability.by_model()

    assert by_model["gpt-4o"]["success_rate"] == 1.0
    assert by_model["gpt-4o-mini"]["success_rate"] == 0.0
    assert by_model["gpt-4o-mini"]["count"] == 2


def test_timeout_and_cancellation_handling():
    latency_service, error_service, reliability = build_env()
    latency_service.record(make_audit("req-1", "openai", "gpt-4o", "succeeded"))
    latency_service.record(make_audit("req-2", "openai", "gpt-4o", "timed_out"))
    latency_service.record(make_audit("req-3", "openai", "gpt-4o", "cancelled"))
    error_service.record(
        make_audit("req-2", "openai", "gpt-4o", "timed_out"), TransientLLMError("timeout")
    )

    summary = reliability.summary()

    assert summary["status_counts"] == {"succeeded": 1, "timed_out": 1, "cancelled": 1}
    assert summary["success_rate"] == round(1 / 3, 6)
    assert summary["failure_rate"] == round(2 / 3, 6)
    assert summary["error_type_counts"] == {"TRANSIENT": 1}


def test_empty_dataset():
    _, _, reliability = build_env()

    assert reliability.summary() == {
        "count": 0,
        "status_counts": {},
        "success_rate": 0.0,
        "failure_rate": 0.0,
        "error_type_counts": {},
    }
    assert reliability.by_provider() == {}
    assert reliability.by_model() == {}
    assert reliability.success_rate() == 0.0
    assert reliability.failure_rate() == 0.0


def test_deterministic_results():
    latency_service, error_service, reliability = build_env()
    latency_service.record(make_audit("req-1", "openai", "gpt-4o", "succeeded"))
    latency_service.record(make_audit("req-2", "openai", "gpt-4o", "failed"))
    error_service.record(
        make_audit("req-2", "openai", "gpt-4o", "failed"), PermanentLLMError("bad request")
    )

    first = reliability.summary()
    second = reliability.summary()
    assert first == second

    first_by_provider = reliability.by_provider()
    second_by_provider = reliability.by_provider()
    assert first_by_provider == second_by_provider
