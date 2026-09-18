from datetime import datetime, timezone
from typing import Optional

from .impact_cache_batch_eviction import EVICTED as EVICTION_EVICTED
from .impact_cache_batch_eviction import FAILED as EVICTION_FAILED
from .impact_cache_batch_eviction import LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionService
from .impact_cache_batch_reconciliation import (
    CANDIDATE_UNAVAILABLE,
    LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationService,
)
from .impact_cache_batch_refresh import FAILED as REFRESH_FAILED
from .impact_cache_batch_refresh import REFRESHED as REFRESH_REFRESHED
from .impact_cache_batch_refresh import LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshService
from .impact_cache_warming import LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService
from .models import (
    AgentTaskRecoveryPreflightDependencyImpactCacheLifecycleAction,
    AgentTaskRecoveryPreflightDependencyImpactCacheLifecycleResult,
)

NONE = "none"
REFRESHED = "refreshed"
EVICTED = "evicted"
UNAVAILABLE = "unavailable"
FAILED = "failed"
LIFECYCLE_ACTIONS = frozenset({NONE, REFRESHED, EVICTED, UNAVAILABLE, FAILED})


class InvalidAgentTaskRecoveryPreflightDependencyImpactCacheLifecycleError(ValueError):
    """Raised when maintain() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencyImpactCacheLifecycleService:
    """Runs one explicit maintenance pass over a task's dependency-impact
    cache by orchestrating today's services -- never a workflow
    framework, scheduler or background job (Rule): maintain() is one
    synchronous call, and whoever calls it owns the cadence. It contains
    no cache, trust, dependency or eviction logic of its own; each phase
    is a delegate:
      1. identify   -- #3's warming service (active_preflight_ids()):
                       the task's relevant preflights, unless the caller
                       names some;
      2. reconcile  -- #9's batch reconciliation plan(): a READ-ONLY
                       consistency classification of each preflight
                       through the trusted-snapshot gate (validation);
      3. refresh    -- #10's batch refresh, and only for the preflights
                       the plan classified refreshable (stale, missing,
                       inconsistent), through #7's refresh(); never
                       overwrites a newer entry and never stores from an
                       untrusted snapshot (those are UNAVAILABLE, so they
                       are not even attempted);
      4. evict      -- #11's batch eviction, AFTER refresh so freshly
                       rebuilt entries are valid and therefore protected;
                       it removes only what #5's rules prove obsolete and
                       never the current valid entry of an active
                       preflight;
      5. metrics    -- #4's summary(), attached read-only. Hits, misses,
                       invalidations and warmings are already recorded by
                       the cache and warming paths at the moment they
                       happen; this pass adds none, so nothing is counted
                       twice or invented.
    Export (#12) is deliberately NOT part of this pass: it is an explicit
    read-only capability a caller invokes on its own, so maintenance
    never silently produces data.

    Phases are isolated: a phase that raises is recorded in phase_errors
    and the pass carries on (a failed plan skips the refresh, which has no
    candidates, but eviction still runs); per-item failures inside a phase
    are already isolated by the delegates. What succeeded is never
    discarded. Per preflight the net action is chosen FAILED > EVICTED >
    REFRESHED > UNAVAILABLE > NONE, so a failure is never masked.

    Preserves history: the only writes are the delegates' own -- #7's
    replace-in-place with its history event, and #5's removal with its
    audit event; snapshots, versions, integrity/trust records and event
    streams are never deleted. No recovery, scheduling, authorization or
    task-state mutation: no such collaborator is held. Idempotent: a
    second run finds everything consistent and nothing obsolete, so it
    writes nothing.
    """

    def __init__(
        self,
        warming_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheWarmingService,
        batch_reconciliation_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchReconciliationService,
        batch_refresh_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchRefreshService,
        batch_eviction_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionService,
        metrics_service=None,
    ):
        """
        Args:
            warming_service: The real #3 service (relevant preflights).
            batch_reconciliation_service: The real #9 service (plan()).
            batch_refresh_service: The real #10 service.
            batch_eviction_service: The real #11 service.
            metrics_service: Optional #4 metrics service (duck-typed,
                summary() only).
        All four delegates are required, with no defaults: a default one
        would silently hold none of the task's real cache or preflights.
        """
        self._warming_service = warming_service
        self._batch_reconciliation_service = batch_reconciliation_service
        self._batch_refresh_service = batch_refresh_service
        self._batch_eviction_service = batch_eviction_service
        self._metrics_service = metrics_service

    def maintain(
        self, task_id: str, preflight_ids: Optional[list] = None
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheLifecycleResult:
        """Reconcile, refresh and evict task_id's cache for the named
        preflights (default: its relevant ones; eviction then covers every
        cached entry of the task).

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheLifecycleError:
                If task_id is not a non-empty string, or preflight_ids is
                given and is not a list/tuple of non-empty strings
        """
        self._require_text(task_id, "task_id")
        requested = None
        if preflight_ids is not None:
            if not isinstance(preflight_ids, (list, tuple)):
                raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheLifecycleError(
                    "preflight_ids must be a list or tuple when given"
                )
            for preflight_id in preflight_ids:
                self._require_text(preflight_id, "preflight_id")
            requested = tuple(dict.fromkeys(preflight_ids))

        errors = []

        try:  # 1. identify
            ids = list(requested) if requested is not None else list(self._warming_service.active_preflight_ids(task_id)[0])
        except Exception as error:
            ids = []
            errors.append(("identify", str(error)))

        plan = None
        try:  # 2. reconcile (read-only)
            plan = self._batch_reconciliation_service.plan(task_id, ids)
        except Exception as error:
            errors.append(("reconcile", str(error)))
        candidates = {c.preflight_id: c for c in plan.candidates} if plan is not None else {}

        refresh = None
        refreshable = [c.preflight_id for c in (plan.candidates if plan is not None else ()) if c.refreshable]
        failed_ids: dict = {}
        if refreshable:  # 3. refresh
            try:
                refresh = self._batch_refresh_service.refresh(task_id, refreshable)
            except Exception as error:
                errors.append(("refresh", str(error)))
                failed_ids.update({preflight_id: f"refresh phase failed: {error}" for preflight_id in refreshable})
        refresh_items = {i.preflight_id: i for i in refresh.items} if refresh is not None else {}

        eviction = None
        try:  # 4. evict
            eviction = self._batch_eviction_service.evict(
                task_id, self._batch_eviction_service.plan(task_id, list(requested) if requested is not None else None)
            )
        except Exception as error:
            errors.append(("evict", str(error)))
        eviction_items = {i.preflight_id: i for i in eviction.items} if eviction is not None else {}

        metrics = None
        if self._metrics_service is not None:  # 5. metrics (read-only)
            try:
                metrics = self._metrics_service.summary(task_id)
            except Exception as error:
                errors.append(("metrics", str(error)))

        actions = [
            self._action(pid, candidates.get(pid), refresh_items.get(pid), eviction_items.get(pid), failed_ids.get(pid))
            for pid in sorted(set(ids) | set(refresh_items) | set(eviction_items) | set(failed_ids))
        ]

        def count(name):
            return sum(1 for action in actions if action.action == name)

        return AgentTaskRecoveryPreflightDependencyImpactCacheLifecycleResult(
            task_id=task_id, requested_preflight_ids=requested, actions=tuple(actions), total=len(actions),
            none_count=count(NONE), refreshed_count=count(REFRESHED), evicted_count=count(EVICTED),
            unavailable_count=count(UNAVAILABLE), failed_count=count(FAILED), plan=plan, refresh=refresh,
            eviction=eviction, phase_errors=tuple(errors), metrics=metrics, maintained_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _action(preflight_id, candidate, refresh_item, eviction_item, phase_failure):
        classification = candidate.classification if candidate is not None else None
        refresh_status = refresh_item.status if refresh_item is not None else None
        eviction_status = eviction_item.status if eviction_item is not None else None
        reasons = tuple(
            (refresh_item.reasons if refresh_item is not None else ())
            + (eviction_item.reasons if eviction_item is not None and eviction_status != "skipped" else ())
        ) or (candidate.reasons if candidate is not None else ())

        if phase_failure is not None or REFRESH_FAILED == refresh_status or EVICTION_FAILED == eviction_status:
            action, reasons = FAILED, ((phase_failure,) if phase_failure is not None else reasons)
        elif eviction_status == EVICTION_EVICTED:
            action = EVICTED
        elif refresh_status == REFRESH_REFRESHED:
            action = REFRESHED
        elif classification == CANDIDATE_UNAVAILABLE or (classification is None and eviction_item is None):
            action = UNAVAILABLE  # untrusted/absent evidence, or nothing at all is known about it
        else:
            action = NONE  # consistent, or an entry eviction judged protected: nothing was changed
        return AgentTaskRecoveryPreflightDependencyImpactCacheLifecycleAction(
            preflight_id=preflight_id, action=action, classification=classification, refresh_status=refresh_status,
            eviction_status=eviction_status, reasons=reasons,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheLifecycleError(
                f"{field_name} is required and must be a non-empty string"
            )
