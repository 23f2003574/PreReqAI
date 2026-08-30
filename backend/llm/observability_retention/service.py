from datetime import datetime, timedelta, timezone

from ..cost import LLMCostService
from ..cost_analytics import LLMCostAnalyticsService
from ..request_errors import LLMRequestErrorService
from ..request_latency import LLMRequestLatencyService
from ..usage import LLMUsageService
from ..usage_aggregation import LLMUsageAggregationService

DEFAULT_RETENTION = timedelta(days=30)


class InvalidRetentionError(ValueError):
    """Raised when configure() is given a non-positive retention period."""


class RetentionBoundaryError(ValueError):
    """Raised when purge_before() is asked to delete data newer than the
    configured retention boundary."""


class _BeforeFilteredUsage:
    """Adapts a Commit #6 usage service's records(scope_id) to only those
    recorded before a cutoff -- lets usage/cost aggregation stay bounded
    without changing those services' own interfaces (the same adapter
    pattern Commit #9's dashboard already uses for latency)."""

    def __init__(self, usage_service: LLMUsageService, cutoff):
        self._usage_service = usage_service
        self._cutoff = cutoff

    def records(self, scope_id: str = None) -> tuple:
        return tuple(
            record
            for record in self._usage_service.records(scope_id)
            if record.recorded_at < self._cutoff
        )


class LLMObservabilityRetentionService:
    """Keeps Commits #1-#10's raw observability records bounded, without a
    second storage system.

    No retention configuration already existed in backend.llm (backend.
    session's is a separate subsystem this repository has never imported
    from), so configure()/retention() are the minimal mechanism this
    commit needs to add. Purging is never automatic: purge_before() only
    ever runs when a caller names an exact scope and cutoff, and always
    refuses to delete anything newer than the configured retention
    boundary. aggregate_before() reuses Commit #9/#10's own by_provider/
    by_model grouping (via a small time-bounded adapter) so a historical
    total survives purging with provider/model identity intact.
    """

    def __init__(
        self,
        usage_service: LLMUsageService,
        cost_service: LLMCostService,
        latency_service: LLMRequestLatencyService,
        error_service: LLMRequestErrorService = None,
        default_retention: timedelta = DEFAULT_RETENTION,
    ):
        self._usage_service = usage_service
        self._cost_service = cost_service
        self._latency_service = latency_service
        self._error_service = error_service
        self._default_retention = default_retention
        self._overrides = {}

    def configure(self, scope, retention_period: timedelta):
        if retention_period.total_seconds() <= 0:
            raise InvalidRetentionError("retention_period must be positive")
        self._overrides[scope] = retention_period

    def retention(self, scope) -> dict:
        """The configured retention boundary for scope (or the default)."""
        period = self._overrides.get(scope, self._default_retention)
        return {
            "scope": scope,
            "retention_period": period,
            "configured": scope in self._overrides,
        }

    def aggregate_before(self, scope, timestamp) -> dict:
        """Usage/cost totals for everything recorded before timestamp,
        broken out by provider and by model -- read-only, nothing is purged."""
        filtered_usage = _BeforeFilteredUsage(self._usage_service, timestamp)
        usage_analytics = LLMUsageAggregationService(filtered_usage)
        cost_analytics = LLMCostAnalyticsService(filtered_usage, self._cost_service)

        return {
            "usage": {
                "totals": usage_analytics.totals(scope),
                "by_provider": usage_analytics.by_provider(scope),
                "by_model": usage_analytics.by_model(scope),
            },
            "cost": {
                "totals": cost_analytics.total(scope),
                "by_provider": cost_analytics.by_provider(scope),
                "by_model": cost_analytics.by_model(scope),
            },
        }

    def purge_before(self, scope, timestamp) -> dict:
        """Aggregate, then delete, everything for scope recorded before timestamp.

        Refuses if timestamp falls inside the configured retention window --
        raw data newer than that boundary is never deleted, no matter what
        is asked.
        """
        boundary = datetime.now(timezone.utc) - self.retention(scope)["retention_period"]
        if timestamp > boundary:
            raise RetentionBoundaryError(
                f"cannot purge data newer than the retention boundary "
                f"{boundary.isoformat()} for scope {scope!r}"
            )

        aggregate = self.aggregate_before(scope, timestamp)

        removed = {
            "usage": self._usage_service.purge_before(timestamp, scope_id=scope),
            "latency": self._latency_service.purge_before(timestamp, scope=scope),
            "error": (
                self._error_service.purge_before(timestamp, scope=scope)
                if self._error_service is not None
                else 0
            ),
        }

        return {
            "scope": scope,
            "purged_before": timestamp,
            "removed": removed,
            "aggregate": aggregate,
        }
