from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional

from .impact_cache_eviction import LLMAgentTaskRecoveryPreflightDependencyImpactCacheEvictionService
from .models import (
    AgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionItem,
    AgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionPlan,
    AgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionResult,
    AgentTaskRecoveryPreflightDependencyImpactCacheEvictionPlan,
)

EVICTED = "evicted"
SKIPPED = "skipped"
FAILED = "failed"
BATCH_EVICTION_STATUSES = frozenset({EVICTED, SKIPPED, FAILED})


class InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionError(ValueError):
    """Raised when plan()/evict() is given invalid arguments, or evict() is
    given a plan built for a different task."""


class LLMAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionService:
    """Evicts several of a task's obsolete cache entries in one explicit
    call -- never another cleanup worker or retention framework (Rule):
    the rules, the retention window and cutoff, and the per-entry
    apply-and-recheck step are all #5's eviction service. That service
    already classifies entries by the same staleness signals #2's
    reconciliation uses (superseded snapshot/version or preflight,
    invalidated preflight, dependency-change events) plus its retention
    window for entries that are not provably consumable, and it PROTECTS
    the current valid entry of an active preflight at any age; this class
    only narrows that plan to the requested preflights, applies each
    candidate through #5's evict_candidate(), and reports per entry.

    Each entry is applied in isolation (Rule): #5 re-checks it at apply
    time, so an entry that became valid or was replaced since planning is
    SKIPPED, never evicted; a removal that raises is that entry's FAILED
    item and the loop continues, so earlier evictions are kept. Protected
    entries and requested preflights with no entry appear as SKIPPED items
    with their reasons, so the report accounts for everything asked about.

    plan() is read-only. evict() removes derived cache entries only, and
    #5 appends one history event per real eviction; no snapshot, version,
    integrity/trust record, preflight, schedule or task event is touched,
    and no recovery/scheduling/authorization mutation is possible (no
    such collaborator is held). Idempotent: a second run finds nothing
    left to evict, and replaying a plan reports its entries SKIPPED.
    """

    def __init__(self, eviction_service: LLMAgentTaskRecoveryPreflightDependencyImpactCacheEvictionService = None):
        """
        Args:
            eviction_service: The real #5 service, wired with the cache,
                the #2 invalidation service (for the full staleness
                signals) and, optionally, an event service for history.
        """
        self._eviction_service = (
            eviction_service
            if eviction_service is not None
            else LLMAgentTaskRecoveryPreflightDependencyImpactCacheEvictionService()
        )

    def plan(
        self, task_id: str, preflight_ids: Optional[list] = None, before: Optional[datetime] = None
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionPlan:
        """Propose which cached entries to evict for the named preflights
        (default: every entry of task_id) -- read-only. `before` is #5's
        retention cutoff (default: now minus its retention window).

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionError:
                If task_id is not a non-empty string, preflight_ids is
                given and is not a list/tuple of non-empty strings, or
                before is given and is not a datetime
        """
        self._require_text(task_id, "task_id")
        requested = None
        if preflight_ids is not None:
            if not isinstance(preflight_ids, (list, tuple)):
                raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionError(
                    "preflight_ids must be a list or tuple when given"
                )
            for preflight_id in preflight_ids:
                self._require_text(preflight_id, "preflight_id")
            requested = tuple(dict.fromkeys(preflight_ids))
        if before is not None and not isinstance(before, datetime):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionError("before must be a datetime when given")

        base = self._eviction_service.plan(task_id, before=before)
        unmatched = ()
        if requested is not None:
            wanted = set(requested)
            base = replace(
                base,
                eligible=tuple(c for c in base.eligible if c.preflight_id in wanted),
                protected=tuple(p for p in base.protected if p.preflight_id in wanted),
            )
            present = {c.preflight_id for c in base.eligible} | {p.preflight_id for p in base.protected}
            unmatched = tuple(preflight_id for preflight_id in requested if preflight_id not in present)
        return AgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionPlan(
            task_id=task_id, plan=base, requested_preflight_ids=requested, unmatched_preflight_ids=unmatched,
            planned_at=datetime.now(timezone.utc),
        )

    def evict(
        self, task_id: str, plan: Optional[AgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionPlan] = None
    ) -> AgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionResult:
        """Evict every planned candidate that is still evictable right now
        (plan defaults to a fresh plan(task_id)). Idempotent.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionError:
                If task_id is not a non-empty string, or plan is not a
                batch eviction plan built for task_id
        """
        self._require_text(task_id, "task_id")
        if plan is None:
            plan = self.plan(task_id)
        elif (
            not isinstance(plan, AgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionPlan)
            or not isinstance(plan.plan, AgentTaskRecoveryPreflightDependencyImpactCacheEvictionPlan)
            or plan.task_id != task_id
        ):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionError(
                f"plan must be a batch eviction plan built for task_id {task_id!r}"
            )

        def item(status, preflight_id, reasons, snapshot_id=None, version=None):
            return AgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionItem(
                preflight_id=preflight_id, status=status, snapshot_id=snapshot_id, version=version, reasons=tuple(reasons)
            )

        items = []
        for candidate in plan.plan.eligible:
            try:
                bucket, result = self._eviction_service.evict_candidate(task_id, candidate, plan.plan.before)
            except Exception as error:
                items.append(item(FAILED, candidate.preflight_id, (f"eviction failed: {error}",), candidate.snapshot_id, candidate.version))
                continue
            if bucket == "evicted":
                items.append(item(EVICTED, candidate.preflight_id, result.reasons, result.snapshot_id, result.version))
            elif bucket == "already_evicted":
                items.append(item(SKIPPED, candidate.preflight_id, ("the entry was already gone",), candidate.snapshot_id, candidate.version))
            else:  # newly_protected: valid, or replaced by a fresher entry, since planning
                items.append(item(SKIPPED, candidate.preflight_id, (result.reason,), result.snapshot_id, result.version))
        for protection in plan.plan.protected:
            items.append(item(SKIPPED, protection.preflight_id, (protection.reason,), protection.snapshot_id, protection.version))
        for preflight_id in plan.unmatched_preflight_ids:
            items.append(item(SKIPPED, preflight_id, ("no cached entry exists for this preflight",)))

        def count(status):
            return sum(1 for entry in items if entry.status == status)

        return AgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionResult(
            task_id=task_id, plan=plan, items=tuple(items), total=len(items), evicted_count=count(EVICTED),
            skipped_count=count(SKIPPED), failed_count=count(FAILED), evicted_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencyImpactCacheBatchEvictionError(
                f"{field_name} is required and must be a non-empty string"
            )
