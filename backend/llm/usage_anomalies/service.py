from datetime import datetime, timezone

from ..cost_analytics import LLMCostAnalyticsService
from ..request_latency import LLMRequestLatencyService
from ..usage_aggregation import LLMUsageAggregationService
from .models import (
    COST,
    CRITICAL,
    ERROR_RATE,
    LATENCY,
    METRICS,
    MODERATE,
    NORMAL,
    TOKENS,
    UNKNOWN,
    LLMUsageAnomaly,
)

SUCCEEDED = "succeeded"


class LLMUsageAnomalyService:
    """Detects spikes by comparing a period's metrics against its own recent history.

    Reuses Commit #1's latency records and Commit #9/#10's usage/cost
    period aggregation end to end -- no new telemetry, no time-series
    store of its own beyond the anomaly records this produces. Analysis is
    read-only and deterministic: the same scope/period/history always
    classifies the same way, and nothing here ever switches a provider or
    takes any action.
    """

    def __init__(
        self,
        usage_analytics: LLMUsageAggregationService,
        cost_analytics: LLMCostAnalyticsService,
        latency_service: LLMRequestLatencyService,
        history_periods: int = 3,
        moderate_threshold: float = 0.5,
        critical_threshold: float = 1.5,
    ):
        self._usage_analytics = usage_analytics
        self._cost_analytics = cost_analytics
        self._latency_service = latency_service
        self._history_periods = history_periods
        self._moderate_threshold = moderate_threshold
        self._critical_threshold = critical_threshold
        self._anomalies = {}
        self._by_scope_metric = {}
        self._counter = 0

    def _latency_window(self, scope, start, end) -> list:
        return [
            record
            for record in self._latency_service.records(scope)
            if start <= record.recorded_at <= end
        ]

    def _metric_value(self, metric: str, scope, start, end):
        """(value, has_data) for one metric over [start, end]."""
        if metric == TOKENS:
            totals = self._usage_analytics.by_period(scope, start, end)
            return float(totals["total_tokens"]), totals["count"] > 0

        if metric == COST:
            summary = self._cost_analytics.by_period(scope, start, end)
            total_cost = sum(summary["by_currency"].values())
            has_data = summary["count"] > 0 or summary["unpriced_count"] > 0
            return float(total_cost), has_data

        if metric == LATENCY:
            records = self._latency_window(scope, start, end)
            if not records:
                return 0.0, False
            return sum(record.duration for record in records) / len(records), True

        if metric == ERROR_RATE:
            records = self._latency_window(scope, start, end)
            if not records:
                return 0.0, False
            failed = sum(1 for record in records if record.status != SUCCEEDED)
            return failed / len(records), True

        raise ValueError(f"unsupported metric {metric!r}")

    def _history_windows(self, start, end) -> list:
        """history_periods windows of the same length, nearest-first, before start."""
        duration = end - start
        windows = []
        window_end = start
        for _ in range(self._history_periods):
            window_start = window_end - duration
            windows.append((window_start, window_end))
            window_end = window_start
        return windows

    def _severity(self, deviation: float) -> str:
        if deviation > self._critical_threshold:
            return CRITICAL
        if deviation > self._moderate_threshold:
            return MODERATE
        return NORMAL

    def _detect_one(self, scope, metric: str, start, end) -> LLMUsageAnomaly:
        observed, _ = self._metric_value(metric, scope, start, end)

        baseline_values = []
        for window_start, window_end in self._history_windows(start, end):
            value, has_data = self._metric_value(metric, scope, window_start, window_end)
            if not has_data:
                baseline_values = None
                break
            baseline_values.append(value)

        if not baseline_values:
            baseline, deviation, severity = None, None, UNKNOWN
        else:
            baseline = round(sum(baseline_values) / len(baseline_values), 6)
            if baseline == 0:
                deviation = 0.0 if observed == 0 else float("inf")
            else:
                deviation = round((observed - baseline) / baseline, 6)
            severity = self._severity(deviation)

        self._counter += 1
        anomaly = LLMUsageAnomaly(
            anomaly_id=f"anomaly-{self._counter}",
            scope=scope,
            metric=metric,
            observed=round(observed, 6),
            baseline=baseline,
            deviation=deviation,
            severity=severity,
            detected_at=datetime.now(timezone.utc),
        )
        anomaly.validate()
        return anomaly

    def detect(self, scope, period) -> list:
        """Classify every supported metric for scope over period=(start, end)."""
        start, end = period
        if start > end:
            raise ValueError("period start must not be after end")

        results = [self._detect_one(scope, metric, start, end) for metric in sorted(METRICS)]

        for anomaly in results:
            self._anomalies[anomaly.anomaly_id] = anomaly
            self._by_scope_metric.setdefault((scope, anomaly.metric), []).append(anomaly.anomaly_id)

        return results

    def by_metric(self, scope, metric: str) -> list:
        """Every anomaly ever detect()'d for this exact scope/metric, in order."""
        return [
            self._anomalies[anomaly_id]
            for anomaly_id in self._by_scope_metric.get((scope, metric), [])
        ]

    def critical(self, scope) -> list:
        """Every recorded CRITICAL anomaly for scope, across all metrics."""
        return [
            anomaly
            for anomaly in self._anomalies.values()
            if anomaly.scope == scope and anomaly.severity == CRITICAL
        ]
