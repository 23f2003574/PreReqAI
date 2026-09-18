from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.agent_task_events.retention import DEFAULT_RETENTION_WINDOW

from .impact_cache import LLMAgentTaskRecoveryPreflightDependencyImpactCacheService
from .models import (
    AgentTaskRecoveryPreflightDependencyImpactCacheEvictionCandidate,
    AgentTaskRecoveryPreflightDependencyImpactCacheEvictionPlan,
    AgentTaskRecoveryPreflightDependencyImpactCacheEvictionProtection,
    AgentTaskRecoveryPreflightDependencyImpactCacheEvictionResult,
)

IMPACT_CACHE_EVICTED_EVENT_TYPE = "dependency_impact_cache_evicted"

PROTECTED_VALID = "current valid entry for an active preflight"
PROTECTED_WITHIN_RETENTION = "not currently consumable, but within the retention window"
EXPIRED_UNPROVABLE = "not provably consumable and older than the retention window"
REPLACED_SINCE_PLAN = "entry was replaced by a fresher one since the plan was built"


class InvalidAgentTaskRecoveryPreflightDependencyImpactCacheEvictionError(ValueError):
    """Raised when plan()/evict() is given invalid arguments, or evict()
    is given a plan built for a different task."""


class LLMAgentTaskRecoveryPreflightDependencyImpactCacheEvictionService:
    """Bounds the #1 cache by removing entries nothing can consume any
    more -- never a generic cache manager or external storage (Rule): the
    only thing removed is a cache entry, through #1's own evict(); the
    plan/apply split, the retention window and its inclusive `before`
    cutoff, and the evicted/already_evicted/newly_protected buckets all
    mirror backend.agent_task_events.LLMAgentTaskEventRetentionService,
    and the default window IS that module's own DEFAULT_RETENTION_WINDOW
    (30 days), not a new number (Rule: "Prefer existing retention/cleanup
    policies instead of hard-coded arbitrary TTLs").

    Each entry is classified in this order:
      1. Provably obsolete -- evicted regardless of age. This is exactly
         the set of reasons #2's invalidation service reports through its
         read-only stale_reasons(): the entry's snapshot/version is no
         longer current, its preflight was invalidated or superseded, or
         a dependency-change event postdates it. Without an invalidation
         service, only the snapshot/version check (#1's is_current()) is
         available.
      2. Currently valid -- PROTECTED, always, at any age (Rule: "Never
         evict the currently valid cache entry for an active preflight").
         "Valid" is #1's own peek(): current identity and, where a trust
         or integrity service is wired, still trusted.
      3. Anything else -- neither provably obsolete nor provably valid
         (e.g. its snapshot currently fails trust, which may yet
         recover): kept for the retention window, then evicted once it is
         older than `before`. This is the only place age matters.

    plan() is read-only (Rule) with respect to the cache and to recovery
    state (peek() and the staleness signals are reads; a trust validation
    appends its usual history record, as it does everywhere). evict()
    re-classifies every candidate at apply time, so a plan gone stale
    (an entry recomputed or made valid since) can never cause a valid
    entry to be removed, and re-running a plan is idempotent.

    Preserves audit/history (Rule): eviction removes derived cache
    entries only. It holds no reference to snapshots, versions,
    integrity/signing/trust history, preflights, schedules or the task
    event stream, so nothing reconciliation or audit needs is touched --
    an evicted result is always reproducible from the untouched
    snapshot, and #2's invalidation history and #4's metric events stay
    exactly as recorded. With an event_service, each actual eviction is
    also appended once, as references, under
    IMPACT_CACHE_EVICTED_EVENT_TYPE (best-effort; a failure never blocks
    eviction).
    """

    def __init__(
        self,
        cache_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheService = None,
        invalidation_service=None,
        event_service=None,
        retention_window: timedelta = DEFAULT_RETENTION_WINDOW,
    ):
        """
        Args:
            cache_service: Defaults to a fresh #1 cache; pass the real one.
            invalidation_service: Optional #2 invalidation service (duck-
                typed, stale_reasons() only). Without it only an entry's
                snapshot/version currency is checked.
            event_service: Optional LLMAgentTaskEventService (emit() only).
            retention_window: How long an entry that is not provably
                consumable is kept; defaults to the event retention
                window.
        """
        self._cache_service = (
            cache_service if cache_service is not None else LLMAgentTaskRecoveryPreflightDependencyImpactCacheService()
        )
        self._invalidation_service = invalidation_service
        self._event_service = event_service
        self._retention_window = retention_window

    def plan(
        self, task_id: str, before: Optional[datetime] = None
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheEvictionPlan:
        """Propose which of task_id's cached entries to evict -- read-only.

        before is the retention cutoff: an entry cached at or before it is
        older than the window (the same inclusive boundary the event
        retention service uses). Defaults to now minus retention_window.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheEvictionError:
                If task_id is not a non-empty string, or before is given
                and is not a datetime
        """
        self._require_text(task_id, "task_id")
        if before is not None and not isinstance(before, datetime):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheEvictionError("before must be a datetime when given")
        effective_before = before if before is not None else datetime.now(timezone.utc) - self._retention_window

        eligible, protected = [], []
        for entry in self._cache_service.list_entries(task_id):
            reasons, protection = self._classify(task_id, entry, effective_before)
            if reasons:
                eligible.append(self._candidate(entry, reasons))
            else:
                protected.append(self._protection(entry, protection))
        return AgentTaskRecoveryPreflightDependencyImpactCacheEvictionPlan(
            task_id=task_id, before=effective_before, eligible=tuple(eligible), protected=tuple(protected),
            planned_at=datetime.now(timezone.utc),
        )

    def evict(
        self, task_id: str, plan: Optional[AgentTaskRecoveryPreflightDependencyImpactCacheEvictionPlan] = None
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheEvictionResult:
        """Evict every plan.eligible entry that is still evictable right
        now (plan defaults to a fresh plan(task_id)). Idempotent.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheEvictionError:
                If task_id is not a non-empty string, or plan is not a
                plan built for task_id
        """
        self._require_text(task_id, "task_id")
        if plan is None:
            plan = self.plan(task_id)
        elif not isinstance(plan, AgentTaskRecoveryPreflightDependencyImpactCacheEvictionPlan) or plan.task_id != task_id:
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheEvictionError(
                f"plan must be an eviction plan built for task_id {task_id!r}"
            )

        current = {entry.preflight_id: entry for entry in self._cache_service.list_entries(task_id)}
        evicted, already_evicted, newly_protected = [], [], []
        for candidate in plan.eligible:
            entry = current.get(candidate.preflight_id)
            if entry is None:
                already_evicted.append(candidate)
                continue
            if (entry.snapshot_id, entry.version) != (candidate.snapshot_id, candidate.version):
                newly_protected.append(self._protection(entry, REPLACED_SINCE_PLAN))
                continue
            reasons, protection = self._classify(task_id, entry, plan.before)
            if not reasons:
                newly_protected.append(self._protection(entry, protection))
                continue
            if self._cache_service.evict(task_id, entry.preflight_id):
                evicted.append(self._candidate(entry, reasons))
                self._record(task_id, entry, reasons)
            else:
                already_evicted.append(candidate)

        return AgentTaskRecoveryPreflightDependencyImpactCacheEvictionResult(
            plan=plan, evicted=tuple(evicted), already_evicted=tuple(already_evicted),
            newly_protected=tuple(newly_protected), evicted_at=datetime.now(timezone.utc),
        )

    def _classify(self, task_id: str, entry, before: datetime) -> tuple:
        """(eviction reasons, protection reason) -- exactly one is empty."""
        if self._invalidation_service is not None:
            obsolete = tuple(self._invalidation_service.stale_reasons(task_id, entry))
        else:
            obsolete = () if self._cache_service.is_current(entry) else ("snapshot/version is no longer the preflight's current one",)
        if obsolete:
            return obsolete, None
        if self._cache_service.peek(task_id, entry.preflight_id) is not None:
            return (), PROTECTED_VALID
        if entry.cached_at <= before:
            return (EXPIRED_UNPROVABLE,), None
        return (), PROTECTED_WITHIN_RETENTION

    def _record(self, task_id: str, entry, reasons: tuple) -> None:
        if self._event_service is None:
            return
        try:
            self._event_service.emit(
                task_id,
                IMPACT_CACHE_EVICTED_EVENT_TYPE,
                payload={
                    "preflight_id": entry.preflight_id, "snapshot_id": entry.snapshot_id, "version": entry.version,
                    "cached_at": entry.cached_at.isoformat(), "reasons": list(reasons),
                },
            )
        except Exception:
            pass  # history is best-effort; it must never block an eviction

    @staticmethod
    def _candidate(entry, reasons: tuple) -> AgentTaskRecoveryPreflightDependencyImpactCacheEvictionCandidate:
        return AgentTaskRecoveryPreflightDependencyImpactCacheEvictionCandidate(
            task_id=entry.task_id, preflight_id=entry.preflight_id, snapshot_id=entry.snapshot_id,
            version=entry.version, cached_at=entry.cached_at, reasons=tuple(reasons),
        )

    @staticmethod
    def _protection(entry, reason: str) -> AgentTaskRecoveryPreflightDependencyImpactCacheEvictionProtection:
        return AgentTaskRecoveryPreflightDependencyImpactCacheEvictionProtection(
            task_id=entry.task_id, preflight_id=entry.preflight_id, snapshot_id=entry.snapshot_id,
            version=entry.version, reason=reason,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheEvictionError(
                f"{field_name} is required and must be a non-empty string"
            )
