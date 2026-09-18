from datetime import datetime, timezone
from typing import Optional

from .impact_cache import LLMAgentTaskRecoveryPreflightDependencyImpactCacheService
from .impact_cache_refresh import CURRENT, NEWER_ENTRY, REFRESHED as REFRESH_REFRESHED
from .impact_cache_refresh import LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService
from .impact_cache_warming import LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService
from .models import (
    AgentTaskRecoveryPreflightDependencyImpactCacheBatchOutcome,
    AgentTaskRecoveryPreflightDependencyImpactCacheBatchResult,
)

CONSISTENT = "consistent"
REFRESHED = "refreshed"
INVALIDATED = "invalidated"
UNAVAILABLE = "unavailable"
BATCH_STATUSES = frozenset({CONSISTENT, REFRESHED, INVALIDATED, UNAVAILABLE})


class InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationError(ValueError):
    """Raised when reconcile()/reconcile_active() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationService:
    """Brings a task's cached dependency-impact entries back in line with
    their trusted snapshots across several preflights in one explicit
    call -- never another cache, reconciliation or batch framework (Rule):
    one synchronous loop, every judgement delegated. Which preflights are
    relevant and whether each is still eligible (current, not
    invalidated, not DENY, fresh, has a TRUSTED snapshot) is #3's warming
    service; whether an entry agrees with its snapshot, and rebuilding it
    when it does not, is #7's refresh service (gated on #6's consistency
    check, so the deep check runs exactly once per preflight); removing an
    obsolete entry is #2's invalidation service, or #1's cache directly
    when none is given.

    Per preflight, independently (Rule: one failure must not discard the
    others -- each is wrapped, a failure is that preflight's UNAVAILABLE
    outcome, and the loop continues):
      not eligible, evidence UNTRUSTED  -> UNAVAILABLE, cache left exactly
        as it is (still non-consumable; nothing is fabricated or removed,
        and the untrusted snapshot is never used);
      not eligible otherwise (superseded, invalidated, DENY, stale, no
        snapshot): an existing entry is provably obsolete -> INVALIDATED
        (removed); with no entry -> UNAVAILABLE;
      eligible: refresh() decides --
        already consistent, or a NEWER entry was kept -> CONSISTENT
          (never replaced by older evidence);
        rebuilt (stale/diverged/corrupted/missing)  -> REFRESHED;
        not trusted / could not be rebuilt          -> UNAVAILABLE.

    Preserves history (Rule): nothing here deletes a snapshot, version,
    integrity/trust record or event; the only writes are #7's replace-in-
    place (with its own history event) and, for an obsolete entry, #2's
    removal (with its history). No recovery, scheduling, authorization or
    task-state mutation -- no such collaborator is held. Idempotent: a
    second run finds refreshed entries consistent and removed ones gone,
    so it changes nothing (a removed entry's preflight reports
    UNAVAILABLE the second time, having no entry left to invalidate).

    Compared with #8's precompute, which only builds and skips, this
    also removes obsolete entries and classifies every preflight. As
    there, only a task's latest preflight can be eligible, so an active
    run refreshes at most one entry and INVALIDATES the entries of older,
    superseded ones.
    """

    def __init__(
        self,
        warming_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService = None,
        refresh_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService = None,
        cache_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheService = None,
        invalidation_service=None,
    ):
        """
        Args:
            warming_service: The real #3 service, wired with the preflight
                store and trust/freshness services (the source of
                "relevant" and "eligible"). Required in practice.
            refresh_service: The real #7 service over the same cache.
            cache_service: The SAME #1 cache the refresh service uses
                (entries are read from it and, without an
                invalidation_service, removed through it).
            invalidation_service: Optional #2 service (duck-typed,
                invalidate_for_preflight() only); when given, removals go
                through it so they are recorded in its history.
        """
        self._warming_service = (
            warming_service if warming_service is not None else LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService()
        )
        self._refresh_service = (
            refresh_service if refresh_service is not None else LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService()
        )
        self._cache_service = (
            cache_service if cache_service is not None else LLMAgentTaskRecoveryPreflightDependencyImpactCacheService()
        )
        self._invalidation_service = invalidation_service

    def reconcile(
        self, task_id: str, preflight_ids: Optional[list] = None
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheBatchResult:
        """Reconcile the named preflights (default: task_id's relevant ones).

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationError:
                If task_id is not a non-empty string, or preflight_ids is
                given and is not a list/tuple of non-empty strings
        """
        self._require_text(task_id, "task_id")
        if preflight_ids is not None:
            if not isinstance(preflight_ids, (list, tuple)):
                raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationError(
                    "preflight_ids must be a list or tuple when given"
                )
            for preflight_id in preflight_ids:
                self._require_text(preflight_id, "preflight_id")
        return self._run(task_id, preflight_ids)

    def reconcile_active(self, task_id: str) -> AgentTaskRecoveryPreflightDependencyImpactCacheBatchResult:
        """Reconcile every relevant preflight of task_id.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationError:
                If task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        return self._run(task_id, None)

    def _run(self, task_id: str, preflight_ids) -> AgentTaskRecoveryPreflightDependencyImpactCacheBatchResult:
        excluded = ()
        if preflight_ids is None:
            preflight_ids, excluded = self._warming_service.active_preflight_ids(task_id)
        outcomes = [self._one(task_id, preflight_id) for preflight_id in dict.fromkeys(preflight_ids)]

        def count(status):
            return sum(1 for outcome in outcomes if outcome.status == status)

        return AgentTaskRecoveryPreflightDependencyImpactCacheBatchResult(
            task_id=task_id, outcomes=tuple(outcomes), total=len(outcomes), consistent_count=count(CONSISTENT),
            refreshed_count=count(REFRESHED), invalidated_count=count(INVALIDATED),
            unavailable_count=count(UNAVAILABLE), excluded_preflight_ids=tuple(excluded),
            reconciled_at=datetime.now(timezone.utc),
        )

    def _one(self, task_id: str, preflight_id: str) -> AgentTaskRecoveryPreflightDependencyImpactCacheBatchOutcome:
        def outcome(status, reasons, snapshot_id=None, version=None, refresh_status=None, categories=()):
            return AgentTaskRecoveryPreflightDependencyImpactCacheBatchOutcome(
                preflight_id=preflight_id, status=status, snapshot_id=snapshot_id, version=version,
                refresh_status=refresh_status, categories=tuple(categories), reasons=tuple(reasons),
            )

        try:
            reasons, snapshot_id, version = self._warming_service.eligibility(task_id, preflight_id)
            if reasons:
                # eligibility() resolves a snapshot only once it reaches the trust gate, so a
                # snapshot_id alongside reasons means the evidence itself is untrusted.
                if snapshot_id is not None:
                    return outcome(UNAVAILABLE, reasons, snapshot_id, version)
                if self._has_entry(task_id, preflight_id):
                    self._invalidate(task_id, preflight_id, reasons)
                    return outcome(INVALIDATED, reasons)
                return outcome(UNAVAILABLE, reasons)

            refreshed = self._refresh_service.refresh(task_id, preflight_id)
        except Exception as error:
            return outcome(UNAVAILABLE, (f"could not be reconciled: {error}",))

        ids = (refreshed.snapshot_id, refreshed.version, refreshed.status, refreshed.categories)
        if refreshed.status == REFRESH_REFRESHED:
            return outcome(REFRESHED, refreshed.reasons, *ids)
        if refreshed.status in (CURRENT, NEWER_ENTRY):
            return outcome(CONSISTENT, refreshed.reasons, *ids)
        return outcome(UNAVAILABLE, refreshed.reasons, *ids)

    def _has_entry(self, task_id: str, preflight_id: str) -> bool:
        return any(entry.preflight_id == preflight_id for entry in self._cache_service.list_entries(task_id))

    def _invalidate(self, task_id: str, preflight_id: str, reasons: tuple) -> None:
        if self._invalidation_service is not None:
            self._invalidation_service.invalidate_for_preflight(task_id, preflight_id)
        else:
            self._cache_service.invalidate(task_id, preflight_id, reason="batch reconciliation: " + "; ".join(reasons))

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationError(
                f"{field_name} is required and must be a non-empty string"
            )
