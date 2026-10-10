import re
from datetime import timedelta

from ..cost_analytics import LLMCostAnalyticsService
from ..provider_reliability import LLMProviderReliabilityService
from ..request_errors import LLMRequestErrorService
from ..request_latency import LLMRequestLatencyService
from ..usage_aggregation import LLMUsageAggregationService
from ..usage_anomalies import COST, ERROR_RATE, LATENCY, TOKENS, LLMUsageAnomalyService

# Same secret-redaction convention already used throughout backend.llm
# (request_latency, request_errors, usage_anomaly_alerts, ...). Kept local
# rather than refactored -- here it guards the one new string this service
# ever introduces: a caller-supplied scope.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)

SUCCEEDED = "succeeded"


def _looks_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


class SecretInScopeError(ValueError):
    """Raised when a scope string looks like it carries a credential."""


class _PeriodFilteredLatency:
    """Adapts Commit #1's latency records to Commit #5's records(scope) contract,
    narrowed to one time window -- lets provider_reliability stay time-aware
    without changing that service's own interface."""

    def __init__(self, latency_service: LLMRequestLatencyService, start, end):
        self._latency_service = latency_service
        self._start = start
        self._end = end

    def records(self, scope=None) -> tuple:
        return tuple(
            record
            for record in self._latency_service.records(scope)
            if self._start <= record.recorded_at <= self._end
        )


class LLMObservabilityDashboardService:
    """One read-only, dashboard-ready aggregate over Commits #1-#7's own analytics.

    Every field is produced by an existing service -- Commit #9's usage
    aggregation, Commit #10's cost analytics, Commit #5's provider
    reliability (via a small time-window adapter, since that service is
    scope- but not period-aware), and Commit #7's anomaly detection -- so
    there is no second telemetry system and nothing here is ever mutated.
    None of those services carry prompt/response/tool-argument content, so
    neither does anything this service returns; the one string a caller
    controls directly, scope, is checked against this repo's secret
    patterns before any query runs.
    """

    def __init__(
        self,
        usage_analytics: LLMUsageAggregationService,
        cost_analytics: LLMCostAnalyticsService,
        latency_service: LLMRequestLatencyService,
        anomaly_service: LLMUsageAnomalyService,
        error_service: LLMRequestErrorService = None,
    ):
        self._usage_analytics = usage_analytics
        self._cost_analytics = cost_analytics
        self._latency_service = latency_service
        self._anomaly_service = anomaly_service
        self._error_service = error_service

    @staticmethod
    def _require_valid_period(period):
        start, end = period
        if start > end:
            raise ValueError("period start must not be after end")
        return start, end

    @staticmethod
    def _require_safe_scope(scope):
        if scope is not None and _looks_secret(scope):
            raise SecretInScopeError(f"scope {scope!r} looks like it carries a credential")

    def _period_latency_records(self, scope, start, end) -> tuple:
        return _PeriodFilteredLatency(self._latency_service, start, end).records(scope)

    def _reliability(self, start, end) -> LLMProviderReliabilityService:
        return LLMProviderReliabilityService(
            _PeriodFilteredLatency(self._latency_service, start, end), self._error_service
        )

    def _latency_summary(self, records) -> dict:
        if not records:
            return {"count": 0, "average_duration": None}
        return {
            "count": len(records),
            "average_duration": round(sum(r.duration for r in records) / len(records), 6),
        }

    @staticmethod
    def _error_rate(records):
        if not records:
            return None
        failed = sum(1 for record in records if record.status != SUCCEEDED)
        return round(failed / len(records), 6)

    def _metric_value(self, metric: str, scope, start, end):
        """A single scalar for one metric over [start, end]; None when there's no data."""
        if metric == TOKENS:
            totals = self._usage_analytics.by_period(scope, start, end)
            return float(totals["total_tokens"]) if totals["count"] else None

        if metric == COST:
            summary = self._cost_analytics.by_period(scope, start, end)
            if summary["count"] == 0 and summary["unpriced_count"] == 0:
                return None
            return float(sum(summary["by_currency"].values()))

        records = self._period_latency_records(scope, start, end)
        if metric == LATENCY:
            return self._latency_summary(records)["average_duration"]
        if metric == ERROR_RATE:
            return self._error_rate(records)

        raise ValueError(f"unsupported metric {metric!r}")

    @staticmethod
    def _daily_buckets(start, end) -> list:
        one_day = timedelta(days=1)
        if end - start <= one_day:
            return [(start, end)]

        buckets = []
        cursor = start
        while cursor < end:
            bucket_end = min(cursor + one_day, end)
            buckets.append((cursor, bucket_end))
            cursor = bucket_end
        return buckets

    def summary(self, scope, period) -> dict:
        """The full dashboard aggregate for scope over period."""
        self._require_safe_scope(scope)
        start, end = self._require_valid_period(period)

        records = self._period_latency_records(scope, start, end)

        return {
            "usage": self._usage_analytics.by_period(scope, start, end),
            "cost": self._cost_analytics.by_period(scope, start, end),
            "latency": self._latency_summary(records),
            "error_rate": self._error_rate(records),
            "provider_reliability": self._reliability(start, end).summary(scope),
            "anomalies": self._anomaly_service.detect(scope, period),
        }

    def timeseries(self, scope, metric: str, period) -> list:
        """One value per day-sized bucket across period; None where a bucket has no data."""
        self._require_safe_scope(scope)
        start, end = self._require_valid_period(period)

        return [
            {"start": bucket_start, "end": bucket_end, "value": self._metric_value(metric, scope, bucket_start, bucket_end)}
            for bucket_start, bucket_end in self._daily_buckets(start, end)
        ]

    def providers(self, scope, period) -> dict:
        """Provider/model reliability breakdown for scope over period."""
        self._require_safe_scope(scope)
        start, end = self._require_valid_period(period)

        reliability = self._reliability(start, end)
        return {
            "by_provider": reliability.by_provider(scope),
            "by_model": reliability.by_model(scope),
        }

    def anomalies(self, scope, period) -> list:
        """Commit #7 anomaly detection for scope over period, unchanged."""
        self._require_safe_scope(scope)
        self._require_valid_period(period)

        return self._anomaly_service.detect(scope, period)
