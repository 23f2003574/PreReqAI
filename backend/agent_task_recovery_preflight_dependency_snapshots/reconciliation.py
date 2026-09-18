from datetime import datetime, timezone

from .models import CHANGED, INDETERMINATE, UNCHANGED, AgentTaskRecoveryPreflightDependencySnapshotReconciliation
from .service import LLMAgentTaskRecoveryPreflightDependencySnapshotService


class LLMAgentTaskRecoveryPreflightDependencySnapshotReconciliationService:
    """Classifies one Commit #1 snapshot as UNCHANGED, CHANGED, or
    INDETERMINATE against task_id's CURRENT dependency graph -- never a
    second dependency comparison engine (Rule: "Reuse #1's snapshot
    service plus existing dependency resolution/reconciliation
    infrastructure; do not create another dependency resolver"):
    reconcile() only ever calls Commit #1's own
    LLMAgentTaskRecoveryPreflightDependencySnapshotService.diff(), which
    itself already does the one live resolver/dependency-service call --
    nothing here re-traverses an edge or re-classifies a lifecycle state
    itself.

    Fail-closed on a genuine resolution failure (Rule: "Clearly
    distinguish unchanged, changed, and indeterminate states"): diff()'s
    own live read is wrapped in a broad `except Exception` (the same
    fail-closed discipline backend.agent_task_recovery_schedule_dependencies'
    own reconciliation.py already establishes for a comparable case) --
    status is then INDETERMINATE, reliable=False, reason names the
    failure, and every per-dependency field is empty rather than a
    fabricated partial comparison. A missing/mismatched-task_id
    snapshot_id is a caller error, not an indeterminate result: that
    check happens first, via Commit #1's own get(), and its own
    InvalidAgentTaskRecoveryPreflightDependencySnapshotError propagates
    unwrapped (Rule: "exact task/snapshot binding").

    Never mutates the snapshot, never executes/reschedules/authorizes
    recovery (Rule): this class holds no reference to anything that
    could -- only Commit #1's own read-only diff()/get().

    Deterministic and idempotent (Rule): see AgentTaskRecoveryPreflight
    DependencySnapshotReconciliation's own docstring -- no observation
    history is ever written, so a repeated reconcile() call against an
    unchanged graph always reproduces the exact same result.
    """

    def __init__(
        self,
        snapshot_service: LLMAgentTaskRecoveryPreflightDependencySnapshotService = None,
        schedule_dependency_reconciliation_service=None,
        version_service=None,
        integrity_service=None,
        signing_service=None,
        trust_service=None,
        trust_change_service=None,
        impact_cache_service=None,
        impact_cache_invalidation_service=None,
    ):
        """
        Args:
            snapshot_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightDependencySnapshotService;
                pass the real instance holding a task's actual snapshots
                for reconcile() to ever find one.
            schedule_dependency_reconciliation_service: Optional, duck-
                typed (never imported here, so this package never
                depends on backend.agent_task_recovery_schedule_
                dependencies), consumed only by reconcile_for_schedule()
                -- Rule: "Feed the result into existing preflight/
                schedule reconciliation where appropriate". Its own
                reconcile(task_id, schedule_id) method is called
                verbatim, never re-derived.
            version_service: Optional Commit #3
                LLMAgentTaskRecoveryPreflightDependencySnapshotVersionService.
                When given, reconcile() looks the compared snapshot_id up
                via its own list_versions(task_id, preflight_id) and
                attaches the matching version number to the result (Rule:
                "Integrate reconciliation so results identify the
                compared snapshot version") -- None when the snapshot was
                never versioned, never fabricated.
        """
        self._snapshot_service = (
            snapshot_service if snapshot_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotService()
        )
        self._schedule_dependency_reconciliation_service = schedule_dependency_reconciliation_service
        self._version_service = version_service
        self._integrity_service = integrity_service
        self._signing_service = signing_service
        self._trust_service = trust_service
        # Optional Commit #8 LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService
        # (duck-typed, only check() is called). When given, it SUPERSEDES
        # trust_service as reconcile()'s own trust gate below (Rule:
        # "Integrate with ... reconciliation so a trust change can
        # invalidate its previous dependency evidence") -- checking for
        # drift, not merely a fresh trust_service.validate() a second time.
        self._trust_change_service = trust_change_service
        # Optional LLMAgentTaskRecoveryPreflightDependencyImpactCacheService
        # (duck-typed, only get()/put() are called). Consulted only AFTER
        # the trust gate above, so a cache hit never bypasses it; any
        # cache failure falls back to the fresh diff below.
        self._impact_cache_service = impact_cache_service
        # Optional LLMAgentTaskRecoveryPreflightDependencyImpactCacheInvalidationService
        # (duck-typed, only reconcile() is called), run immediately before
        # every cache lookup so a change signalled since the entry was
        # computed is removed first; if it fails, the cache is not
        # consulted at all (fail closed to a fresh diff).
        self._impact_cache_invalidation_service = impact_cache_invalidation_service

    def is_current(self, task_id: str, snapshot_id: str) -> bool:
        """Shorthand for reconcile(task_id, snapshot_id).status ==
        UNCHANGED -- False (fail-closed) for both CHANGED and
        INDETERMINATE."""
        return self.reconcile(task_id, snapshot_id).status == UNCHANGED

    def reconcile(self, task_id: str, snapshot_id: str) -> AgentTaskRecoveryPreflightDependencySnapshotReconciliation:
        """Compare task_id's exact, already-persisted snapshot_id against
        task_id's CURRENT dependency graph, right now.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotError:
                Propagated, not wrapped, from Commit #1's own get()/
                diff() if task_id/snapshot_id is not a non-empty string,
                or snapshot_id names no recorded snapshot for task_id
        """
        snapshot = self._snapshot_service.get(task_id, snapshot_id)
        if snapshot is None:
            # Reuses Commit #1's own diff() purely to raise its own,
            # already-worded InvalidAgentTaskRecoveryPreflightDependency
            # SnapshotError for this exact case, rather than duplicating
            # that error message a second way.
            self._snapshot_service.diff(task_id, snapshot_id)

        version = self._resolve_version(task_id, snapshot.preflight_id, snapshot_id)
        integrity = self._integrity_service.verify(task_id, snapshot_id) if self._integrity_service is not None else None
        signature = self._signing_service.verify_signature(task_id, snapshot_id) if self._signing_service is not None else None

        if self._trust_change_service is not None:
            change = self._trust_change_service.check(task_id, snapshot_id)
            if not change.current_trust.trusted:
                return AgentTaskRecoveryPreflightDependencySnapshotReconciliation(
                    task_id=task_id, snapshot_id=snapshot_id, preflight_id=snapshot.preflight_id,
                    status=INDETERMINATE, reliable=False,
                    added=(), removed=(), resolved=(), blocked=(), changed=(),
                    reason=(
                        f"snapshot is not trusted: {'; '.join(change.current_trust.blocking_reasons)}"
                        + (f" (changed dimensions: {', '.join(change.changed_dimensions)})" if change.changed else "")
                    ),
                    reconciled_at=self._now(), version=version, integrity=integrity, signature=signature,
                )
        elif self._trust_service is not None:
            trust = self._trust_service.validate(task_id, snapshot_id)
            if not trust.trusted:
                return AgentTaskRecoveryPreflightDependencySnapshotReconciliation(
                    task_id=task_id, snapshot_id=snapshot_id, preflight_id=snapshot.preflight_id,
                    status=INDETERMINATE, reliable=False,
                    added=(), removed=(), resolved=(), blocked=(), changed=(),
                    reason=f"snapshot is not trusted: {'; '.join(trust.blocking_reasons)}",
                    reconciled_at=self._now(), version=version, integrity=integrity, signature=signature,
                )

        if self._impact_cache_service is not None:
            try:
                if self._impact_cache_invalidation_service is not None:
                    self._impact_cache_invalidation_service.reconcile(task_id)
                cached = self._impact_cache_service.get(task_id, snapshot.preflight_id)
            except Exception:
                cached = None
            if cached is not None and cached.snapshot_id == snapshot_id:
                return cached

        try:
            diff = self._snapshot_service.diff(task_id, snapshot_id)
        except Exception as error:
            return AgentTaskRecoveryPreflightDependencySnapshotReconciliation(
                task_id=task_id, snapshot_id=snapshot_id, preflight_id=snapshot.preflight_id,
                status=INDETERMINATE, reliable=False,
                added=(), removed=(), resolved=(), blocked=(), changed=(),
                reason=f"dependency graph could not be resolved: {error}",
                reconciled_at=self._now(), version=version, integrity=integrity, signature=signature,
            )

        result = AgentTaskRecoveryPreflightDependencySnapshotReconciliation(
            task_id=task_id, snapshot_id=snapshot_id, preflight_id=diff.preflight_id,
            status=CHANGED if diff.changed else UNCHANGED, reliable=True,
            added=diff.added, removed=diff.removed, resolved=diff.resolved,
            blocked=diff.newly_blocked, changed=diff.state_changed,
            reason=None,
            reconciled_at=self._now(), version=version, integrity=integrity, signature=signature,
        )

        if self._impact_cache_service is not None:
            try:
                self._impact_cache_service.put(task_id, snapshot.preflight_id, result)
            except Exception:
                pass  # caching is best-effort; the fresh result is still correct
        return result

    def _resolve_version(self, task_id: str, preflight_id: str, snapshot_id: str):
        if self._version_service is None:
            return None
        for entry in self._version_service.list_versions(task_id, preflight_id):
            if entry.snapshot_id == snapshot_id:
                return entry.version
        return None

    def reconcile_for_schedule(self, task_id: str, schedule_id: str, snapshot_id: str) -> dict:
        """Combine this class's own reconcile() with an optional,
        already-existing preflight/schedule dependency reconciliation
        service's own reconcile(task_id, schedule_id) -- Rule: "Feed the
        result into existing preflight/schedule reconciliation where
        appropriate". Returns {"snapshot": ..., "schedule": ...};
        "schedule" is None when no schedule_dependency_reconciliation_
        service was configured -- never fabricated.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotError:
                Propagated from this class's own reconcile()
        """
        snapshot_result = self.reconcile(task_id, snapshot_id)
        schedule_result = None
        if self._schedule_dependency_reconciliation_service is not None:
            schedule_result = self._schedule_dependency_reconciliation_service.reconcile(task_id, schedule_id)
        return {"snapshot": snapshot_result, "schedule": schedule_result}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
