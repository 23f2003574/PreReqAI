import pytest

from backend.session import (
    ExecutionAlertDeduplicationService,
    ExecutionAlertRuleService,
    ExecutionAlertService,
    ExecutionMetricsService,
    ExecutionObservabilityAlertFingerprint,
    ExecutionObservabilityAlertFingerprintError as Error,
    ExecutionObservabilityAlertRule,
)


class _FakeRuntimeService:
    def __init__(self, statuses=None):
        self._statuses = dict(statuses or {"runtime-1": "RUNNING", "runtime-2": "RUNNING"})

    def status(self, runtime_id):
        if runtime_id not in self._statuses:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return self._statuses[runtime_id]


def _build():
    runtime_service = _FakeRuntimeService()
    metrics_service = ExecutionMetricsService(runtime_service)
    alert_rule_service = ExecutionAlertRuleService(metrics_service)
    alert_service = ExecutionAlertService(alert_rule_service, metrics_service)
    dedup_service = ExecutionAlertDeduplicationService()

    return metrics_service, alert_rule_service, alert_service, dedup_service


def _register_rule(alert_rule_service, metric="latency_ms", severity="WARNING"):
    rule = ExecutionObservabilityAlertRule(
        name=f"{metric} rule", metric=metric, operator="GT", threshold=100, severity=severity
    )
    alert_rule_service.register(rule)

    return rule


class TestExecutionAlertDeduplicationService:
    def test_fingerprint_generation(self):
        metrics_service, alert_rule_service, alert_service, dedup_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        alert = alert_service.trigger("runtime-1", rule.rule_id)

        fingerprint = dedup_service.fingerprint(alert)

        assert isinstance(fingerprint, str)
        assert fingerprint

    def test_deterministic_fingerprints(self):
        metrics_service, alert_rule_service, alert_service, dedup_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        first_alert = alert_service.trigger("runtime-1", rule.rule_id)

        metrics_service.record("runtime-1", "latency_ms", 200, "ms")
        second_alert = alert_service.trigger("runtime-1", rule.rule_id)

        assert first_alert.alert_id != second_alert.alert_id
        assert dedup_service.fingerprint(first_alert) == dedup_service.fingerprint(second_alert)

    def test_duplicate_detection(self):
        metrics_service, alert_rule_service, alert_service, dedup_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        alert = alert_service.trigger("runtime-1", rule.rule_id)

        assert dedup_service.duplicate(alert) is False

        dedup_service.record(alert)

        assert dedup_service.duplicate(alert) is True

    def test_occurrence_counting(self):
        metrics_service, alert_rule_service, alert_service, dedup_service = _build()

        rule = _register_rule(alert_rule_service)

        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        first_alert = alert_service.trigger("runtime-1", rule.rule_id)
        first_record = dedup_service.record(first_alert)

        assert isinstance(first_record, ExecutionObservabilityAlertFingerprint)
        assert first_record.occurrence_count == 1
        assert first_record.first_seen == first_alert.triggered_at
        assert first_record.last_seen == first_alert.triggered_at

        metrics_service.record("runtime-1", "latency_ms", 200, "ms")
        second_alert = alert_service.trigger("runtime-1", rule.rule_id)
        second_record = dedup_service.record(second_alert)

        assert second_record.occurrence_count == 2
        assert second_record.first_seen == first_alert.triggered_at
        assert second_record.last_seen == second_alert.triggered_at
        assert dedup_service.occurrences(dedup_service.fingerprint(second_alert)) == 2

    def test_occurrences_of_unknown_fingerprint_is_zero(self):
        _, _, _, dedup_service = _build()

        assert dedup_service.occurrences("does-not-exist") == 0

    def test_condition_isolation_by_rule(self):
        metrics_service, alert_rule_service, alert_service, dedup_service = _build()

        latency_rule = _register_rule(alert_rule_service, metric="latency_ms")
        memory_rule = _register_rule(alert_rule_service, metric="memory_mb")

        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        metrics_service.record("runtime-1", "memory_mb", 150, "mb")

        latency_alert = alert_service.trigger("runtime-1", latency_rule.rule_id)
        memory_alert = alert_service.trigger("runtime-1", memory_rule.rule_id)

        assert dedup_service.fingerprint(latency_alert) != dedup_service.fingerprint(memory_alert)

        dedup_service.record(latency_alert)

        assert dedup_service.duplicate(memory_alert) is False

    def test_condition_isolation_by_runtime(self):
        metrics_service, alert_rule_service, alert_service, dedup_service = _build()

        rule = _register_rule(alert_rule_service)

        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        metrics_service.record("runtime-2", "latency_ms", 150, "ms")

        runtime_one_alert = alert_service.trigger("runtime-1", rule.rule_id)
        runtime_two_alert = alert_service.trigger("runtime-2", rule.rule_id)

        assert dedup_service.fingerprint(runtime_one_alert) != dedup_service.fingerprint(runtime_two_alert)

        dedup_service.record(runtime_one_alert)

        assert dedup_service.duplicate(runtime_two_alert) is False

    def test_reset(self):
        metrics_service, alert_rule_service, alert_service, dedup_service = _build()

        rule = _register_rule(alert_rule_service)
        metrics_service.record("runtime-1", "latency_ms", 150, "ms")
        alert = alert_service.trigger("runtime-1", rule.rule_id)

        dedup_service.record(alert)
        key = dedup_service.fingerprint(alert)

        removed = dedup_service.reset(key)

        assert removed.fingerprint == key
        assert dedup_service.occurrences(key) == 0
        assert dedup_service.duplicate(alert) is False

    def test_reset_is_idempotent(self):
        _, _, _, dedup_service = _build()

        assert dedup_service.reset("does-not-exist") is None

    def test_fingerprint_requires_valid_alert_shape(self):
        _, _, _, dedup_service = _build()

        with pytest.raises(Error):
            dedup_service.fingerprint(object())
