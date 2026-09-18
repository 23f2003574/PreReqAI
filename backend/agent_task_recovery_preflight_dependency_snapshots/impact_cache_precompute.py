from datetime import datetime, timezone
from typing import Optional

from .impact_cache_refresh import CURRENT, NEWER_ENTRY, NOT_TRUSTED, REFRESHED as REFRESH_REFRESHED
from .impact_cache_refresh import LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService
from .impact_cache_warming import LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService
from .models import (
    AgentTaskRecoveryPreflightDependencyImpactCachePrecomputeOutcome,
    AgentTaskRecoveryPreflightDependencyImpactCachePrecomputeResult,
)

SKIPPED = "skipped"
REFRESHED = "refreshed"
FAILED = "failed"
PRECOMPUTE_STATUSES = frozenset({SKIPPED, REFRESHED, FAILED})


class InvalidAgentTaskRecoveryPreflightDependencyImpactCachePrecomputeError(ValueError):
    """Raised when precompute()/precompute_active() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencyImpactCachePrecomputeService:
    """Explicitly precomputes dependency-impact results for several of a
    task's preflights in one call -- never a worker, queue or batch
    framework (Rule): it is one synchronous loop over the preflights it is
    given, and whoever calls it owns the cadence. Every judgement reuses an
    existing service: which preflights are relevant and eligible is #3's
    warming service (active_preflight_ids()/eligibility(): current, not
    invalidated, not DENY, fresh, has a TRUSTED snapshot), and every
    rebuild is #7's refresh service, which itself gates on #6's
    consistency check and #1's cache.put().

    Per preflight, in isolation (Rule: one failure must not discard the
    others -- each is wrapped, a failure becomes that preflight's FAILED
    outcome, and the loop always continues):
      ineligible (incl. untrusted/obsolete snapshot) -> SKIPPED, and
        nothing is analysed, so an untrusted or superseded snapshot is
        never used;
      refresh CURRENT (already consistent)           -> SKIPPED;
      refresh REFRESHED                              -> REFRESHED;
      refresh NOT_TRUSTED or NEWER_ENTRY             -> SKIPPED (nothing
        was fabricated, and a newer entry was never replaced);
      refresh NOT_REFRESHED or any exception         -> FAILED.

    Preserves cache/version history: it only ever calls refresh(), so the
    only writes are #7's own (replace-in-place, plus its history event);
    it touches no snapshot, version, integrity or trust record. Never
    mutates recovery, scheduling, authorization or task state -- it holds
    no such collaborator. Idempotent: a second run over unchanged state
    finds everything current, so every outcome is SKIPPED and nothing is
    rewritten.

    precompute(task_id, preflight_ids=None) processes exactly the ids
    given (order kept, duplicates dropped); with None it processes the
    task's relevant preflights, newest first, which is what
    precompute_active() does. Because #2's invalidation treats every
    preflight but the latest as superseded, an active run refreshes at
    most one entry per task; older ones come back SKIPPED.
    """

    def __init__(
        self,
        warming_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService = None,
        refresh_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService = None,
    ):
        """
        Args:
            warming_service: The real #3 warming service, wired with the
                preflight store (and trust/freshness services) -- it is
                the source of "relevant" and "eligible". Required in
                practice: a default one has no preflight store and every
                call would raise.
            refresh_service: The real #7 refresh service over the same
                cache. Defaults to a fresh one.
        """
        self._warming_service = (
            warming_service if warming_service is not None else LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService()
        )
        self._refresh_service = (
            refresh_service if refresh_service is not None else LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService()
        )

    def precompute(
        self, task_id: str, preflight_ids: Optional[list] = None
    ) -> AgentTaskRecoveryPreflightDependencyImpactCachePrecomputeResult:
        """Precompute the named preflights (default: task_id's relevant
        ones).

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCachePrecomputeError:
                If task_id is not a non-empty string, or preflight_ids is
                given and is not a list/tuple of non-empty strings
        """
        self._require_text(task_id, "task_id")
        if preflight_ids is not None:
            if not isinstance(preflight_ids, (list, tuple)):
                raise InvalidAgentTaskRecoveryPreflightDependencyImpactCachePrecomputeError(
                    "preflight_ids must be a list or tuple when given"
                )
            for preflight_id in preflight_ids:
                self._require_text(preflight_id, "preflight_id")
        return self._run(task_id, preflight_ids)

    def precompute_active(self, task_id: str) -> AgentTaskRecoveryPreflightDependencyImpactCachePrecomputeResult:
        """Precompute every relevant preflight of task_id.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCachePrecomputeError:
                If task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        return self._run(task_id, None)

    def _run(self, task_id: str, preflight_ids) -> AgentTaskRecoveryPreflightDependencyImpactCachePrecomputeResult:
        excluded = ()
        if preflight_ids is None:
            preflight_ids, excluded = self._warming_service.active_preflight_ids(task_id)
        ordered = list(dict.fromkeys(preflight_ids))

        outcomes = [self._one(task_id, preflight_id) for preflight_id in ordered]

        def count(status):
            return sum(1 for outcome in outcomes if outcome.status == status)

        return AgentTaskRecoveryPreflightDependencyImpactCachePrecomputeResult(
            task_id=task_id, outcomes=tuple(outcomes), refreshed_count=count(REFRESHED),
            skipped_count=count(SKIPPED), failed_count=count(FAILED), excluded_preflight_ids=tuple(excluded),
            precomputed_at=datetime.now(timezone.utc),
        )

    def _one(self, task_id: str, preflight_id: str) -> AgentTaskRecoveryPreflightDependencyImpactCachePrecomputeOutcome:
        def outcome(status, reasons, snapshot_id=None, version=None, refresh_status=None):
            return AgentTaskRecoveryPreflightDependencyImpactCachePrecomputeOutcome(
                preflight_id=preflight_id, status=status, snapshot_id=snapshot_id, version=version,
                refresh_status=refresh_status, reasons=tuple(reasons),
            )

        try:
            reasons, snapshot_id, version = self._warming_service.eligibility(task_id, preflight_id)
            if reasons:
                return outcome(SKIPPED, reasons, snapshot_id, version)
            refreshed = self._refresh_service.refresh(task_id, preflight_id)
        except Exception as error:
            return outcome(FAILED, (f"precompute failed: {error}",))

        ids = (refreshed.snapshot_id, refreshed.version, refreshed.status)
        if refreshed.status == REFRESH_REFRESHED:
            return outcome(REFRESHED, refreshed.reasons, *ids)
        if refreshed.status in (CURRENT, NOT_TRUSTED, NEWER_ENTRY):
            return outcome(SKIPPED, refreshed.reasons, *ids)
        return outcome(FAILED, refreshed.reasons, *ids)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCachePrecomputeError(
                f"{field_name} is required and must be a non-empty string"
            )
