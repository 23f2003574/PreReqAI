from ..request_errors import LLMRequestErrorService, UnknownRequestErrorMetricError
from ..request_latency import LLMRequestLatencyService

SUCCEEDED = "succeeded"


class LLMProviderReliabilityService:
    """Reliability rates from Commit #1's latency records and Commit #2's error records.

    Latency records are the exhaustive lifecycle source: one is recorded
    for every completed request regardless of outcome, so counts and
    rates are derived from them; a request's error record (recorded only
    when one exists) is joined in purely to enrich the summary with why a
    failure happened, and error_service is optional -- omit it and
    error_type_counts is always empty rather than failing.
    """

    def __init__(
        self,
        latency_service: LLMRequestLatencyService,
        error_service: LLMRequestErrorService = None,
    ):
        self._latency_service = latency_service
        self._error_service = error_service

    def _records(self, scope: str = None) -> tuple:
        return self._latency_service.records(scope)

    @staticmethod
    def _rates(records) -> tuple:
        total = len(records)
        if not total:
            return 0.0, 0.0
        succeeded = sum(1 for latency in records if latency.status == SUCCEEDED)
        success_rate = succeeded / total
        return round(success_rate, 6), round(1.0 - success_rate, 6)

    @staticmethod
    def _status_counts(records) -> dict:
        counts = {}
        for latency in records:
            counts[latency.status] = counts.get(latency.status, 0) + 1
        return counts

    def _error_type_counts(self, records) -> dict:
        if self._error_service is None:
            return {}

        counts = {}
        for latency in records:
            try:
                error_metric = self._error_service.get(latency.request_id)
            except UnknownRequestErrorMetricError:
                continue
            counts[error_metric.error_type] = counts.get(error_metric.error_type, 0) + 1
        return counts

    def _summarize(self, records) -> dict:
        success_rate, failure_rate = self._rates(records)
        return {
            "count": len(records),
            "status_counts": self._status_counts(records),
            "success_rate": success_rate,
            "failure_rate": failure_rate,
            "error_type_counts": self._error_type_counts(records),
        }

    def summary(self, scope: str = None) -> dict:
        return self._summarize(self._records(scope))

    def _group_by(self, scope, key) -> dict:
        groups = {}
        for latency in self._records(scope):
            groups.setdefault(key(latency), []).append(latency)
        return {group_key: self._summarize(records) for group_key, records in groups.items()}

    def by_provider(self, scope: str = None) -> dict:
        """Reliability summaries grouped by provider, preserving provider identity."""
        return self._group_by(scope, key=lambda latency: latency.provider)

    def by_model(self, scope: str = None) -> dict:
        """Reliability summaries grouped by model, preserving model identity."""
        return self._group_by(scope, key=lambda latency: latency.model)

    def success_rate(self, scope: str = None) -> float:
        rate, _ = self._rates(self._records(scope))
        return rate

    def failure_rate(self, scope: str = None) -> float:
        _, rate = self._rates(self._records(scope))
        return rate
