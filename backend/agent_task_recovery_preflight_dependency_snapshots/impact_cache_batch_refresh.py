from datetime import datetime, timezone
from typing import Optional

from .impact_cache_batch_reconciliation import LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationService
from .impact_cache_refresh import REFRESHED as REFRESH_REFRESHED
from .impact_cache_refresh import LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService
from .models import (
    AgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshItem,
    AgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshResult,
)

REFRESHED = "refreshed"
SKIPPED = "skipped"
FAILED = "failed"
BATCH_REFRESH_STATUSES = frozenset({REFRESHED, SKIPPED, FAILED})


class InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshError(ValueError):
    """Raised when refresh()/refresh_stale() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshService:
    """Runs a selective refresh over several preflights -- never another
    batch, worker or cache framework (Rule): one synchronous loop.
    Candidates come from #9's batch reconciliation service, through its
    read-only plan() (so choosing candidates writes nothing), and every
    rebuild is #7's single-preflight refresh().

    Only preflights the plan classifies STALE, MISSING or INCONSISTENT
    are refreshed; everything else is SKIPPED with the plan's reasons:
      CURRENT      -> untouched (already-current entries are never
                      rewritten, so a repeat run changes nothing);
      UNAVAILABLE  -> untrusted or absent evidence: nothing is built and
                      nothing fabricated, so an untrusted snapshot is
                      never used to store an impact;
      OBSOLETE     -> an entry for a preflight that is no longer eligible.
                      Deviation from the literal "invalidated" wording,
                      on purpose: rebuilding an entry for a superseded or
                      invalidated preflight would only recreate what
                      #9/#5 remove. An entry #2 already invalidated for a
                      dependency change shows up as MISSING and IS
                      rebuilt.
    A refresh the refresh service itself declines (already current after a
    race, untrusted, a NEWER entry kept -- never replaced by older
    evidence) is SKIPPED; one that cannot complete, or any exception, is
    FAILED. Each preflight is processed in isolation, so a failure never
    discards another's stored result.

    Preserves cache/version history: the only writes are #7's replace-in-
    place plus its own history event; no snapshot, version, integrity or
    trust record is touched, and nothing is removed (unlike #9's
    reconcile()). No recovery, scheduling, authorization or task-state
    mutation -- no such collaborator is held.

    refresh_stale(task_id) refreshes every relevant preflight of the task
    (refresh() with no ids); refresh(task_id, preflight_ids) does exactly
    the ones named.
    """

    def __init__(
        self,
        batch_reconciliation_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationService = None,
        refresh_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService = None,
    ):
        """
        Args:
            batch_reconciliation_service: The real #9 service (its plan()
                supplies the candidates). Required in practice.
            refresh_service: The real #7 service over the same cache.
        """
        self._refresh_service = (
            refresh_service if refresh_service is not None else LLMAgentTaskRecoveryPreflightDependencyImpactCacheRefreshService()
        )
        self._batch_reconciliation_service = (
            batch_reconciliation_service
            if batch_reconciliation_service is not None
            else LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationService(
                refresh_service=self._refresh_service
            )
        )

    def refresh(
        self, task_id: str, preflight_ids: Optional[list] = None
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshResult:
        """Refresh the refreshable ones among the named preflights
        (default: task_id's relevant ones).

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshError:
                If task_id is not a non-empty string, or preflight_ids is
                given and is not a list/tuple of non-empty strings
        """
        self._require_text(task_id, "task_id")
        if preflight_ids is not None:
            if not isinstance(preflight_ids, (list, tuple)):
                raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshError(
                    "preflight_ids must be a list or tuple when given"
                )
            for preflight_id in preflight_ids:
                self._require_text(preflight_id, "preflight_id")
        return self._run(task_id, preflight_ids)

    def refresh_stale(self, task_id: str) -> AgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshResult:
        """Refresh every relevant preflight of task_id that needs it.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshError:
                If task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        return self._run(task_id, None)

    def _run(self, task_id: str, preflight_ids) -> AgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshResult:
        plan = self._batch_reconciliation_service.plan(task_id, preflight_ids)
        items = [self._one(task_id, candidate) for candidate in plan.candidates]

        def count(status):
            return sum(1 for item in items if item.status == status)

        return AgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshResult(
            task_id=task_id, items=tuple(items), total=len(items), refreshed_count=count(REFRESHED),
            skipped_count=count(SKIPPED), failed_count=count(FAILED),
            excluded_preflight_ids=plan.excluded_preflight_ids, refreshed_at=datetime.now(timezone.utc),
        )

    def _one(self, task_id: str, candidate) -> AgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshItem:
        def item(status, reasons, snapshot_id=None, version=None, refresh_status=None):
            return AgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshItem(
                preflight_id=candidate.preflight_id, status=status, classification=candidate.classification,
                snapshot_id=snapshot_id, version=version, refresh_status=refresh_status,
                categories=candidate.categories, reasons=tuple(reasons),
            )

        if not candidate.refreshable:
            return item(SKIPPED, candidate.reasons, candidate.snapshot_id, candidate.version)
        try:
            refreshed = self._refresh_service.refresh(task_id, candidate.preflight_id)
        except Exception as error:
            return item(FAILED, (f"refresh failed: {error}",), candidate.snapshot_id, candidate.version)

        ids = (refreshed.snapshot_id, refreshed.version, refreshed.status)
        if refreshed.status == REFRESH_REFRESHED:
            return item(REFRESHED, refreshed.reasons, *ids)
        if refreshed.status in ("current", "not_trusted", "newer_entry"):
            return item(SKIPPED, refreshed.reasons, *ids)
        return item(FAILED, refreshed.reasons, *ids)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshError(
                f"{field_name} is required and must be a non-empty string"
            )
