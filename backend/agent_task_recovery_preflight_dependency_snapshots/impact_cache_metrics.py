from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_events import LLMAgentTaskEventQueryService, LLMAgentTaskEventService

from .models import AgentTaskRecoveryPreflightDependencyImpactCacheMetrics

IMPACT_CACHE_METRIC_EVENT_TYPE = "dependency_impact_cache_metric"

METRIC_HIT = "hit"
METRIC_MISS = "miss"
METRIC_INVALIDATION = "invalidation"
METRIC_WARM = "warm"
METRIC_COMPUTATION_AVOIDED = "computation_avoided"

# Miss reasons the cache itself reports. record_miss() accepts any
# non-empty reason; only "stale" feeds the dedicated stale_misses figure.
MISS_NOT_CACHED = "not_cached"
MISS_STALE = "stale"
MISS_UNTRUSTED = "untrusted"


class InvalidAgentTaskRecoveryPreflightDependencyImpactCacheMetricsError(ValueError):
    """Raised when any operation here is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencyImpactCacheMetricsService:
    """Counts what the #1-#3 dependency-impact cache actually does --
    never a metrics backend or telemetry system (Rule: "No new telemetry
    backend"). Persistence and aggregation are the task family's own
    existing ones: every record_*() appends one event to the task event
    stream through backend.agent_task_events.LLMAgentTaskEventService
    under IMPACT_CACHE_METRIC_EVENT_TYPE, and summary() aggregates them
    back through LLMAgentTaskEventQueryService -- the same reuse pattern
    trust_history.py and impact_cache_invalidation.py already follow.
    There is no counter state on this class, so nothing can drift from
    the record (the "no duplicate metric state" rule
    backend.agent_policy_metrics states for its own audit-derived
    figures).

    Wire a DEDICATED event store for it (the default when none is given)
    rather than sharing the task stream other consumers replay: a cache
    lookup is a read, and recording every hit is a write.

    Append-only, one event per observed occurrence (repository
    convention, see LLMAgentTaskEventService.emit()): nothing here
    dedups. Calling record_hit() three times is three hits, exactly as
    three real lookups are; callers must record only what actually
    happened, which is what the cache/warming/reconcile integration
    does. summary() is a pure, deterministic read: repeating it over
    unchanged events returns the same figures.

    Recording is best-effort at every integration site: the cache,
    warming and reconcile paths swallow any metrics failure, so a broken
    event store can never change a lookup result or a recovery decision.
    Direct callers of this class see its errors normally.

    Never touches raw cache state (Rule): this class holds no reference
    to the cache, snapshots, preflights or any recovery service.
    """

    def __init__(
        self,
        event_service: LLMAgentTaskEventService = None,
        event_query_service: LLMAgentTaskEventQueryService = None,
    ):
        """
        Args:
            event_service: Defaults to a fresh LLMAgentTaskEventService
                over its own in-memory store.
            event_query_service: Defaults to a query service over
                event_service's own store, so summary() always reads what
                record_*() wrote; pass one explicitly only for a store
                the query side reads differently.
        """
        self._event_service = event_service if event_service is not None else LLMAgentTaskEventService()
        self._event_query_service = (
            event_query_service
            if event_query_service is not None
            else LLMAgentTaskEventQueryService(self._event_service.store)
        )

    def record_hit(self, task_id: str, preflight_id: str) -> None:
        """One cache lookup for task_id/preflight_id was served from cache."""
        self._require_ids(task_id, preflight_id)
        self._emit(task_id, METRIC_HIT, preflight_id)

    def record_miss(self, task_id: str, preflight_id: str, reason: str) -> None:
        """One cache lookup was not served from cache, for `reason`
        (e.g. MISS_NOT_CACHED, MISS_STALE, MISS_UNTRUSTED)."""
        self._require_ids(task_id, preflight_id)
        self._require_text(reason, "reason")
        self._emit(task_id, METRIC_MISS, preflight_id, reason=reason)

    def record_invalidation(self, task_id: str, preflight_id: str, reason: Optional[str] = None) -> None:
        """One cached entry was actually removed. reason may be None when
        the remover gave none."""
        self._require_ids(task_id, preflight_id)
        if reason is not None:
            self._require_text(reason, "reason")
        self._emit(task_id, METRIC_INVALIDATION, preflight_id, reason=reason)

    def record_warm(self, task_id: str, preflight_id: str, success: bool) -> None:
        """One warming attempt actually did work: success=True when a
        result was stored, False when it could not be."""
        self._require_ids(task_id, preflight_id)
        if not isinstance(success, bool):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheMetricsError("success must be a bool")
        self._emit(task_id, METRIC_WARM, preflight_id, success=success)

    def record_computation_avoided(self, task_id: str, preflight_id: str) -> None:
        """A caller consumed a cached result instead of running a fresh
        impact analysis."""
        self._require_ids(task_id, preflight_id)
        self._emit(task_id, METRIC_COMPUTATION_AVOIDED, preflight_id)

    def summary(self, task_id: str) -> AgentTaskRecoveryPreflightDependencyImpactCacheMetrics:
        """Aggregate every cache event recorded for task_id. A task with
        none yields all zeros (rates 0.0), never an error.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheMetricsError:
                If task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        events = self._event_query_service.query(task_id=task_id, event_types=[IMPACT_CACHE_METRIC_EVENT_TYPE])

        hits = misses = invalidations = warm_attempts = warm_successes = avoided = 0
        miss_reasons: dict = {}
        for event in events:
            payload = event.payload if isinstance(event.payload, dict) else {}
            metric = payload.get("metric")
            if metric == METRIC_HIT:
                hits += 1
            elif metric == METRIC_MISS:
                misses += 1
                reason = payload.get("reason") or "unspecified"
                miss_reasons[reason] = miss_reasons.get(reason, 0) + 1
            elif metric == METRIC_INVALIDATION:
                invalidations += 1
            elif metric == METRIC_WARM:
                warm_attempts += 1
                warm_successes += 1 if payload.get("success") is True else 0
            elif metric == METRIC_COMPUTATION_AVOIDED:
                avoided += 1

        lookups = hits + misses
        return AgentTaskRecoveryPreflightDependencyImpactCacheMetrics(
            task_id=task_id, hits=hits, misses=misses, lookups=lookups,
            hit_rate=(hits / lookups) if lookups else 0.0, miss_rate=(misses / lookups) if lookups else 0.0,
            stale_misses=miss_reasons.get(MISS_STALE, 0), miss_reasons=dict(sorted(miss_reasons.items())),
            invalidations=invalidations, warm_attempts=warm_attempts, warm_successes=warm_successes,
            warm_failures=warm_attempts - warm_successes,
            warm_success_rate=(warm_successes / warm_attempts) if warm_attempts else 0.0,
            computations_avoided=avoided, generated_at=datetime.now(timezone.utc),
        )

    def _emit(self, task_id: str, metric: str, preflight_id: str, **extra) -> None:
        payload = {"metric": metric, "preflight_id": preflight_id}
        payload.update({key: value for key, value in extra.items() if value is not None})
        self._event_service.emit(task_id, IMPACT_CACHE_METRIC_EVENT_TYPE, payload=payload)

    def _require_ids(self, task_id, preflight_id) -> None:
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheMetricsError(
                f"{field_name} is required and must be a non-empty string"
            )
