from datetime import datetime, timezone

import pytest

from backend.llm.cost import LLMCostService
from backend.llm.cost_analytics import LLMCostAnalyticsService
from backend.llm.usage import LLMUsageRecord
from backend.llm.usage_aggregation import LLMUsageAggregationService
from backend.llm.usage_anomalies import (
    CRITICAL,
    MODERATE,
    TOKENS,
    LLMUsageAnomalyService,
    UnknownUsageAnomalyError,
)
from backend.llm.usage_anomaly_alerts import (
    DuplicateAlertError,
    LLMUsageAnomalyAlertService,
    NotAnomalousError,
    OPEN,
    RESOLVED,
    SecretInAlertMessageError,
    UnknownAlertError,
)

DAY1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
DAY2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
DAY3 = datetime(2026, 1, 3, tzinfo=timezone.utc)
DAY4 = datetime(2026, 1, 4, tzinfo=timezone.utc)
PERIOD = (DAY3, DAY4)


class FakeUsageService:
    def __init__(self, records):
        self._records = records

    def records(self, scope_id=None):
        if scope_id is None:
            return tuple(self._records)
        return tuple(r for r in self._records if r.request_id == scope_id)


class FakeLatencyService:
    def records(self, scope=None):
        return ()


def make_usage_record(usage_id, request_id, tokens, recorded_at):
    return LLMUsageRecord(
        usage_id=usage_id,
        request_id=request_id,
        provider="openai",
        model="gpt-4o",
        input_tokens=tokens,
        output_tokens=0,
        total_tokens=tokens,
        recorded_at=recorded_at,
    )


def build_anomaly_service(scope, day1_tokens, day2_tokens, day3_tokens):
    records = [
        make_usage_record("u1", scope, day1_tokens, DAY1 + (DAY2 - DAY1) / 2),
        make_usage_record("u2", scope, day2_tokens, DAY2 + (DAY3 - DAY2) / 2),
        make_usage_record("u3", scope, day3_tokens, DAY3 + (DAY4 - DAY3) / 2),
    ]
    usage_service = FakeUsageService(records)
    usage_analytics = LLMUsageAggregationService(usage_service)
    cost_service = LLMCostService(usage_service)
    cost_analytics = LLMCostAnalyticsService(usage_service, cost_service)
    return LLMUsageAnomalyService(
        usage_analytics, cost_analytics, FakeLatencyService(), history_periods=2
    )


def find(results, metric):
    return next(r for r in results if r.metric == metric)


def build_env(scope="req-1", day3_tokens=500):
    anomaly_service = build_anomaly_service(scope, 100, 100, day3_tokens)
    alert_service = LLMUsageAnomalyAlertService(anomaly_service)
    return anomaly_service, alert_service


def test_alert_creation():
    anomaly_service, alert_service = build_env()
    critical = find(anomaly_service.detect("req-1", PERIOD), TOKENS)
    assert critical.severity == CRITICAL

    alert = alert_service.create(critical.anomaly_id)

    assert alert.anomaly_id == critical.anomaly_id
    assert alert.severity == CRITICAL
    assert alert.status == OPEN
    assert alert.resolved_at is None
    assert "TOKENS" in alert.message
    assert "req-1" in alert.message


def test_duplicate_prevention():
    anomaly_service, alert_service = build_env()
    critical = find(anomaly_service.detect("req-1", PERIOD), TOKENS)

    first = alert_service.create(critical.anomaly_id)
    with pytest.raises(DuplicateAlertError):
        alert_service.create(critical.anomaly_id)

    alert_service.resolve(first.alert_id)

    # Once resolved, the anomaly can be alerted on again.
    second = alert_service.create(critical.anomaly_id)
    assert second.alert_id != first.alert_id


def test_severity_propagation():
    critical_anomaly_service, alert_service = build_env(scope="req-critical", day3_tokens=400)
    moderate_anomaly_service = build_anomaly_service("req-moderate", 100, 100, 170)

    critical = find(critical_anomaly_service.detect("req-critical", PERIOD), TOKENS)
    moderate = find(moderate_anomaly_service.detect("req-moderate", PERIOD), TOKENS)
    assert critical.severity == CRITICAL
    assert moderate.severity == MODERATE

    moderate_alert_service = LLMUsageAnomalyAlertService(moderate_anomaly_service)

    critical_alert = alert_service.create(critical.anomaly_id)
    moderate_alert = moderate_alert_service.create(moderate.anomaly_id)

    assert critical_alert.severity == CRITICAL
    assert moderate_alert.severity == MODERATE


def test_unresolved_filtering():
    anomaly_service, alert_service = build_env(scope="req-1")
    critical_1 = find(anomaly_service.detect("req-1", PERIOD), TOKENS)
    critical_2 = find(anomaly_service.detect("req-1", PERIOD), TOKENS)

    alert_1 = alert_service.create(critical_1.anomaly_id)
    alert_2 = alert_service.create(critical_2.anomaly_id)

    assert {a.alert_id for a in alert_service.unresolved("req-1")} == {
        alert_1.alert_id,
        alert_2.alert_id,
    }

    alert_service.resolve(alert_1.alert_id)

    assert [a.alert_id for a in alert_service.unresolved("req-1")] == [alert_2.alert_id]
    assert {a.alert_id for a in alert_service.list("req-1")} == {alert_1.alert_id, alert_2.alert_id}


def test_resolution():
    anomaly_service, alert_service = build_env()
    critical = find(anomaly_service.detect("req-1", PERIOD), TOKENS)
    alert = alert_service.create(critical.anomaly_id)

    resolved = alert_service.resolve(alert.alert_id)
    assert resolved.status == RESOLVED
    assert resolved.resolved_at is not None

    # Resolving again is a no-op, not an error.
    resolved_again = alert_service.resolve(alert.alert_id)
    assert resolved_again.resolved_at == resolved.resolved_at

    with pytest.raises(UnknownAlertError):
        alert_service.resolve("does-not-exist")


def test_invalid_anomaly():
    _, alert_service = build_env()

    with pytest.raises(UnknownUsageAnomalyError):
        alert_service.create("does-not-exist")

    anomaly_service = build_anomaly_service("req-normal", 100, 100, 105)
    normal_service = LLMUsageAnomalyAlertService(anomaly_service)
    normal = find(anomaly_service.detect("req-normal", PERIOD), TOKENS)

    with pytest.raises(NotAnomalousError):
        normal_service.create(normal.anomaly_id)


def test_secret_exclusion():
    leaked_scope = "sk-liveAbCdEfGhIjKlMnOpQrSt"
    anomaly_service = build_anomaly_service(leaked_scope, 100, 100, 500)
    alert_service = LLMUsageAnomalyAlertService(anomaly_service)
    critical = find(anomaly_service.detect(leaked_scope, PERIOD), TOKENS)

    with pytest.raises(SecretInAlertMessageError):
        alert_service.create(critical.anomaly_id)

    with pytest.raises(UnknownAlertError):
        alert_service.resolve("alert-1")
