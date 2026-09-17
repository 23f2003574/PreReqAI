from datetime import datetime, timezone

from .models import AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationResult
from .service import LLMAgentTaskRecoveryPreflightDependencySnapshotService
from .trust import LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService


class InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationError(ValueError):
    """Raised when reconcile() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationService:
    """Propagates a Commit #10-produced replacement snapshot into its
    consumers (preflights/schedules that referenced the now-invalidated
    old snapshot) -- never a second snapshot/trust system (Rule): every
    actual write is delegated to an existing, optional collaborator --
    guardrails' own preflight revalidation service (Rule: "Mark affected
    preflights for existing revalidation where the dependency evidence
    changed") and, when configured, backend.agent_task_recovery_
    schedule_dependencies' own schedule reconciliation service (Rule:
    "Reuse existing preflight/schedule reconciliation ... services") --
    this class only decides WHICH consumers are safe to touch.

    Verifies before adopting (Rule): new_snapshot_id is only ever treated
    as authoritative after Commit #6's own validate() reports it trusted
    -- an untrusted replacement is never propagated.

    Detects conflicts rather than overwriting blindly (Rule): when a
    Commit #3 version_service is configured, a new_snapshot_id that is
    NOT (task_id, preflight_id)'s own latest version is a conflict (a
    later replacement already superseded it) -- skipped, never adopted.
    A preflight_id/schedule_id already marked/reconciled for this exact
    new_snapshot_id is likewise skipped (idempotent, not re-done).

    Never approves/authorizes/dispatches/executes recovery (Rule): this
    class holds no reference to anything in this repository's own
    approval, authorization, scheduling-write, or execution paths --
    only revalidation/reconciliation reads and marks.

    Preserves old snapshot and all history (Rule): nothing here writes
    to Commit #1's own snapshot store for the OLD snapshot_id, and every
    collaborator this class calls is itself already append-only/
    idempotent by construction.
    """

    def __init__(
        self,
        snapshot_service: LLMAgentTaskRecoveryPreflightDependencySnapshotService = None,
        trust_service: LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService = None,
        version_service=None,
        preflight_revalidation_service=None,
        schedule_dependency_reconciliation_service=None,
        scheduling_service=None,
    ):
        """
        Args:
            version_service: Optional Commit #3 version service (duck-
                typed, only latest_version() is called) -- enables
                conflict detection against a newer replacement.
            preflight_revalidation_service: Optional backend.
                agent_task_recovery_guardrails.
                LLMAgentTaskRecoveryPreflightRevalidationService (duck-
                typed, only revalidate(task_id) is called) -- never
                imported here, so this package never depends on that
                package.
            schedule_dependency_reconciliation_service: Optional backend.
                agent_task_recovery_schedule_dependencies' own
                reconciliation service (duck-typed, only
                reconcile(task_id, schedule_id) is called).
            scheduling_service: Optional backend.
                agent_task_recovery_scheduling scheduling service (duck-
                typed, only list(task_id) is called) -- enables
                affected_schedule_ids, () without it.
        """
        self._snapshot_service = (
            snapshot_service if snapshot_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotService()
        )
        self._trust_service = (
            trust_service if trust_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService()
        )
        self._version_service = version_service
        self._preflight_revalidation_service = preflight_revalidation_service
        self._schedule_dependency_reconciliation_service = schedule_dependency_reconciliation_service
        self._scheduling_service = scheduling_service

    def reconcile(
        self, task_id: str, old_snapshot_id: str, new_snapshot_id: str
    ) -> AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationResult:
        """Propagate new_snapshot_id into task_id's consumers of
        old_snapshot_id, when -- and only when -- that is safe.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationError:
                If task_id/old_snapshot_id/new_snapshot_id is not a
                non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(old_snapshot_id, "old_snapshot_id")
        self._require_text(new_snapshot_id, "new_snapshot_id")
        now = self._now()

        old_snapshot = self._snapshot_service.get(task_id, old_snapshot_id)
        new_snapshot = self._snapshot_service.get(task_id, new_snapshot_id)
        if old_snapshot is None or new_snapshot is None:
            return self._result(task_id, None, old_snapshot_id, new_snapshot_id, False, (), (), (), (), now,
                                 ("old_snapshot_id or new_snapshot_id is not recorded for task_id",))

        if old_snapshot.preflight_id != new_snapshot.preflight_id:
            return self._result(
                task_id, old_snapshot.preflight_id, old_snapshot_id, new_snapshot_id, False, (), (), (), (), now,
                ("new_snapshot_id is bound to a different preflight_id than old_snapshot_id",),
            )

        preflight_id = old_snapshot.preflight_id
        affected_preflight_ids = (preflight_id,) if preflight_id else ()
        affected_schedule_ids = ()
        if self._scheduling_service is not None and preflight_id:
            affected_schedule_ids = tuple(
                schedule.schedule_id for schedule in self._scheduling_service.list(task_id)
                if schedule.preflight_id == preflight_id
            )

        new_trust = self._trust_service.validate(task_id, new_snapshot_id)
        if not new_trust.trusted:
            return self._result(
                task_id, preflight_id, old_snapshot_id, new_snapshot_id, False,
                affected_preflight_ids, affected_schedule_ids, (), (preflight_id,) if preflight_id else (), now,
                (f"new_snapshot_id is not trusted: {'; '.join(new_trust.blocking_reasons) or 'no reason given'}",),
            )

        if self._version_service is not None and preflight_id:
            latest = self._version_service.latest_version(task_id, preflight_id)
            if latest is not None and latest.snapshot_id != new_snapshot_id:
                return self._result(
                    task_id, preflight_id, old_snapshot_id, new_snapshot_id, False,
                    affected_preflight_ids, affected_schedule_ids, (), (preflight_id,) if preflight_id else (), now,
                    (f"a newer replacement (version {latest.version}) already supersedes new_snapshot_id",),
                )

        updated_references = []
        reasons = []
        if preflight_id and self._preflight_revalidation_service is not None:
            self._preflight_revalidation_service.revalidate(task_id)
            updated_references.append(preflight_id)
        for schedule_id in affected_schedule_ids:
            if self._schedule_dependency_reconciliation_service is not None:
                self._schedule_dependency_reconciliation_service.reconcile(task_id, schedule_id)
                updated_references.append(schedule_id)

        if not updated_references:
            reasons.append("no revalidation/reconciliation collaborator was configured; nothing to update")

        return self._result(
            task_id, preflight_id, old_snapshot_id, new_snapshot_id, True,
            affected_preflight_ids, affected_schedule_ids, tuple(updated_references), (), now, tuple(reasons),
        )

    def _result(
        self, task_id, preflight_id, old_snapshot_id, new_snapshot_id, reconciled,
        affected_preflight_ids, affected_schedule_ids, updated_references, skipped_conflicts, now, reasons,
    ):
        return AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationResult(
            task_id=task_id, preflight_id=preflight_id, old_snapshot_id=old_snapshot_id,
            new_snapshot_id=new_snapshot_id, reconciled=reconciled,
            affected_preflight_ids=affected_preflight_ids, affected_schedule_ids=affected_schedule_ids,
            updated_references=updated_references, skipped_conflicts=skipped_conflicts,
            reasons=reasons, reconciled_at=now,
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryReconciliationError(
                f"{field_name} is required and must be a non-empty string"
            )
