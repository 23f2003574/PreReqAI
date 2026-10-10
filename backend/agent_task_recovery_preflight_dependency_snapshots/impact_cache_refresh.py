from datetime import datetime, timezone

from .impact_cache import LLMAgentTaskRecoveryPreflightDependencyImpactCacheService
from .impact_cache_consistency import (
    CORRUPTED,
    MISMATCHED,
    UNTRUSTED,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService,
)
from .models import (
    AgentTaskRecoveryPreflightDependencyImpactCacheRefreshResult,
    AgentTaskRecoveryPreflightDependencyImpactCacheRefreshSummary,
)
from .reconciliation import LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService

IMPACT_CACHE_REFRESHED_EVENT_TYPE = "dependency_impact_cache_refreshed"

REFRESHED = "refreshed"
CURRENT = "current"
NOT_TRUSTED = "not_trusted"
NEWER_ENTRY = "newer_entry"
NOT_REFRESHED = "not_refreshed"
REFRESH_STATUSES = frozenset({REFRESHED, CURRENT, NOT_TRUSTED, NEWER_ENTRY, NOT_REFRESHED})


class InvalidAgentTaskRecoveryPreflightDependencyImpactCacheRefreshError(ValueError):
    """Raised when refresh()/refresh_stale() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService:
    """Rebuilds an absent, stale or inconsistent cache entry from the
    latest trusted snapshot -- never another cache or analysis engine
    (Rule): the gate is #6's own check(), the latest trusted identity is
    #1's current_identity()/is_trusted(), the recompute is Commit #2's
    reconcile(use_cache=False), and the write is #1's put().

    refresh() decides in this order:
      1. no current snapshot -> NOT_REFRESHED (nothing to refresh from);
      2. check() finds the current snapshot untrusted -> NOT_TRUSTED. The
         entry is left exactly as it is: it stays non-consumable (the
         cache's own get() already misses it) and no result is fabricated;
      3. check() finds nothing -> CURRENT, a no-op that runs no analysis
         (idempotent when the cache is already current);
      4. an existing entry bound to a NEWER version than the latest
         resolved one -> NEWER_ENTRY, kept;
      5. otherwise recompute and store. A corrupted/mismatched entry is
         removed first (its own timestamps cannot be trusted to win the
         put()'s newer-evidence check); any other entry is replaced in
         place, so a failed recompute never loses a valid entry.
    put() never overwrites an entry for the same snapshot/version that was
    computed later, so a concurrent newer write is reported NEWER_ENTRY
    (Rule: never replace a newer valid entry with older evidence). That
    check-and-write is not atomic across processes.

    Unlike #3's warming (which pre-populates only current, usable
    preflights) and #6's repair() (which removes then recomputes), this
    refreshes on demand for a named preflight and only after the
    consistency gate. It performs no recovery, scheduling or authorization
    action and holds no such collaborator. With an event_service each
    actual refresh is appended once as references under
    IMPACT_CACHE_REFRESHED_EVENT_TYPE (best-effort).

    refresh_stale() refreshes every inconsistent preflight check() finds
    for the task -- its cached ones plus, with a preflight_store wired on
    the consistency service, its current preflight -- and only counts the
    consistent ones.
    """

    def __init__(
        self,
        cache_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheService = None,
        consistency_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService = None,
        reconciliation_service: LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService = None,
        event_service=None,
    ):
        """
        Args:
            cache_service: Defaults to a fresh #1 cache; pass the real one.
            consistency_service: Defaults to a fresh #6 service over
                cache_service; pass the real, wired one.
            reconciliation_service: Defaults to a fresh one; pass the real,
                wired one (its snapshot service must hold the snapshots).
            event_service: Optional LLMAgentTaskEventService (emit() only).
        """
        self._cache_service = (
            cache_service if cache_service is not None else LLMAgentTaskRecoveryPreflightDependencyImpactCacheService()
        )
        self._consistency_service = (
            consistency_service
            if consistency_service is not None
            else LLMAgentTaskRecoveryPreflightDependencyImpactCacheConsistencyService(cache_service=self._cache_service)
        )
        self._reconciliation_service = (
            reconciliation_service
            if reconciliation_service is not None
            else LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService()
        )
        self._event_service = event_service

    def refresh(self, task_id: str, preflight_id: str) -> AgentTaskRecoveryPreflightDependencyImpactCacheRefreshResult:
        """Refresh task_id's cached impact for preflight_id if, and only
        if, it is absent, stale or inconsistent.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheRefreshError:
                If task_id or preflight_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        return self._refresh(task_id, preflight_id, self._consistency_service.check(task_id, preflight_id))

    def assess(self, task_id: str, preflight_id: str):
        """The #6 consistency result refresh() would act on for
        preflight_id -- a pure read that refreshes nothing, exposed so
        batch planning reuses this service's own gate.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheRefreshError:
                If task_id or preflight_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        return self._consistency_service.check(task_id, preflight_id)

    def refresh_stale(self, task_id: str) -> AgentTaskRecoveryPreflightDependencyImpactCacheRefreshSummary:
        """Refresh every inconsistent preflight of task_id.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheRefreshError:
                If task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        check = self._consistency_service.check(task_id)
        inconsistent = sorted({violation.preflight_id for violation in check.violations})

        results = []
        for preflight_id in inconsistent:
            per_preflight = self._consistency_service.check(task_id, preflight_id)  # fresh, scoped to this preflight
            results.append(self._refresh(task_id, preflight_id, per_preflight))

        def count(status):
            return sum(1 for result in results if result.status == status)

        return AgentTaskRecoveryPreflightDependencyImpactCacheRefreshSummary(
            task_id=task_id, results=tuple(results), checked_count=len(check.checked_preflight_ids),
            consistent_count=len(check.checked_preflight_ids) - len(inconsistent), refreshed_count=count(REFRESHED),
            not_trusted_count=count(NOT_TRUSTED), newer_entry_count=count(NEWER_ENTRY),
            not_refreshed_count=count(NOT_REFRESHED), refreshed_at=self._now(),
        )

    def _refresh(self, task_id: str, preflight_id: str, check) -> AgentTaskRecoveryPreflightDependencyImpactCacheRefreshResult:
        categories = tuple(sorted({violation.category for violation in check.violations}))

        def outcome(status, reason, snapshot_id=None, version=None, result=None):
            return AgentTaskRecoveryPreflightDependencyImpactCacheRefreshResult(
                task_id=task_id, preflight_id=preflight_id, status=status, snapshot_id=snapshot_id, version=version,
                categories=categories, reasons=(reason,), result=result, refreshed_at=self._now(),
            )

        identity = self._cache_service.current_identity(task_id, preflight_id)
        if identity is None:
            return outcome(NOT_REFRESHED, "the preflight has no current snapshot to refresh from")
        snapshot_id, version = identity
        if UNTRUSTED in categories:
            return outcome(NOT_TRUSTED, "trust in the latest snapshot cannot be established; the cache was left as is", *identity)
        if check.is_consistent:
            return outcome(CURRENT, "the cached impact is already consistent with the latest trusted snapshot", *identity)

        entry = next((e for e in self._cache_service.list_entries(task_id) if e.preflight_id == preflight_id), None)
        if entry is not None and entry.version is not None and version is not None and entry.version > version:
            return outcome(NEWER_ENTRY, "the cached entry is bound to a newer version than the latest resolved one", *identity)

        if entry is not None and {CORRUPTED, MISMATCHED} & set(categories):
            self._cache_service.invalidate(task_id, preflight_id, reason="cache refresh: " + ", ".join(categories))
        try:
            impact = self._reconciliation_service.reconcile(task_id, snapshot_id, use_cache=False)
            stored = self._cache_service.put(task_id, preflight_id, impact)
        except Exception as error:
            return outcome(NOT_REFRESHED, f"impact analysis failed: {error}", *identity)
        if stored is None:
            reason = impact.reason if not impact.reliable else "the snapshot was superseded while refreshing"
            return outcome(NOT_REFRESHED, f"no result could be cached: {reason}", *identity)
        if stored.result.reconciled_at > impact.reconciled_at:
            return outcome(NEWER_ENTRY, "a newer entry was written concurrently and was kept", *identity)

        self._record(task_id, preflight_id, categories, entry, stored)
        return outcome(REFRESHED, "the entry was rebuilt from the latest trusted snapshot", *identity, result=stored.result)

    def _record(self, task_id: str, preflight_id: str, categories: tuple, old, new) -> None:
        if self._event_service is None:
            return
        try:
            self._event_service.emit(
                task_id,
                IMPACT_CACHE_REFRESHED_EVENT_TYPE,
                payload={
                    "preflight_id": preflight_id, "categories": list(categories),
                    "previous_snapshot_id": old.snapshot_id if old is not None else None,
                    "previous_version": old.version if old is not None else None,
                    "snapshot_id": new.snapshot_id, "version": new.version,
                },
            )
        except Exception:
            pass  # history is best-effort; it must never block a refresh

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheRefreshError(
                f"{field_name} is required and must be a non-empty string"
            )
