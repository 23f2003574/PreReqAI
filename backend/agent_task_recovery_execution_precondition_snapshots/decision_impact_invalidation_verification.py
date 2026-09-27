from .decision_change_impact import LLMAgentTaskRecoveryExecutionDecisionChangeImpactService
from .decision_impact_invalidation_audit import LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService
from .decision_impact_staleness import LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import (
    ARTIFACT_FRESH,
    ARTIFACT_STALE,
    IMPACT_INVALIDATION_AUDIT_SCHEMA_VERSION,
    IMPACT_INVALIDATION_VERIFICATION_INVALID,
    IMPACT_INVALIDATION_VERIFICATION_VALID,
    INTEGRITY_VALID,
    AgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationResult,
)

_DECISION_REFERENCING = ("execution_pointer", "reconciliation_result", "lifecycle_result")
_PRECONDITION_KINDS = ("authorization", "execution_snapshot", "recovery_plan", "readiness")


class InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationError(ValueError):
    """Raised when verify() is given invalid arguments."""


class LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationService:
    """Verifies, after the fact, that an impact-invalidation operation
    (#5) produced the expected downstream state -- read-only, comparing
    the operation's audit record (#6) with persisted state read through
    existing services, and never repairing anything:

      * refreshed decision-referencing artifacts (pointer, reconciliation
        and lifecycle results) must now reference the current decision
        (re-checked via change impact #1 + staleness #2);
      * an invalidated preflight must carry a recorded invalidation
        (LLMAgentTaskRecoveryPreflightInvalidationService.get_invalidation);
      * cancelled retries must have no remaining retry schedule
        (LLMAgentTaskRetryScheduler.get_retry_schedule);
      * revalidated/refreshed preconditions must leave the current
        decision passing the existing decision integrity check;
      * skipped, manual-review and failed artifacts must still be
        unresolved; nothing outside the operation may have become stale;
        the audit's recorded remaining state must match the current one.

    Fails closed: when a check's evidence or collaborator is unavailable,
    it is a blocking issue and the verdict is INVALID.
    """

    def __init__(
        self,
        audit_service: LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService = None,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        impact_service: LLMAgentTaskRecoveryExecutionDecisionChangeImpactService = None,
        staleness_service: LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService = None,
        snapshot_service=None,
        preflight_invalidation_service=None,
        retry_scheduler=None,
        integrity_service=None,
    ):
        """All collaborators must share the stores the operation used."""
        self._audit_service = audit_service or LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService()
        self._decision_store = decision_store or LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self._impact_service = impact_service or LLMAgentTaskRecoveryExecutionDecisionChangeImpactService(
            decision_store=self._decision_store, snapshot_service=snapshot_service,
        )
        self._staleness_service = staleness_service or LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService()
        self._snapshot_service = snapshot_service
        self._preflight_service = preflight_invalidation_service
        self._retry_scheduler = retry_scheduler
        self._integrity_service = integrity_service

    def verify(
        self, task_id: str, invalidation_operation_id: str
    ) -> AgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationResult:
        """Verify task_id's impact-invalidation operation.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationError:
                If task_id/invalidation_operation_id is not a non-empty string
        """
        for value, name in ((task_id, "task_id"), (invalidation_operation_id, "invalidation_operation_id")):
            if not value or not isinstance(value, str):
                raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationError(
                    f"{name} is required and must be a non-empty string"
                )

        record = next(
            (r for r in self._audit_service.list(task_id) if r.operation_id == invalidation_operation_id), None
        )
        if record is None:
            return self._result(task_id, invalidation_operation_id, (), (), (), (
                f"impact-invalidation operation {invalidation_operation_id} has no audit record for task {task_id}",
            ))

        mismatches, blocking, verified, unresolved = [], [], [], []
        if record.schema_version != IMPACT_INVALIDATION_AUDIT_SCHEMA_VERSION:
            mismatches.append(f"unsupported audit schema version {record.schema_version!r}")
        if not record.previous_decision_id or not record.current_decision_id:
            blocking.append("the operation does not record its decision change; expected state cannot be established")
            return self._result(task_id, invalidation_operation_id, verified, unresolved, mismatches, blocking)

        impact = self._impact_service.analyze(task_id, record.previous_decision_id, record.current_decision_id)
        staleness = self._staleness_service.check(task_id, impact)
        by_kind = {a.kind: a for a in staleness.artifacts}
        stale_now = {f"{a.kind}:{a.reference}" for a in staleness.artifacts if a.status == ARTIFACT_STALE}
        current = record.current_decision_id

        for outcome in record.applied:
            kind, aid = outcome.artifact_type, outcome.artifact_id
            if kind in _DECISION_REFERENCING:
                artifact = by_kind.get(kind)
                if artifact is None:
                    blocking.append(f"{aid}: its current state cannot be read")
                elif artifact.status == ARTIFACT_FRESH and artifact.reference == current:
                    verified.append(aid)
                else:
                    mismatches.append(
                        f"refreshed {aid} does not reference the current decision {current} "
                        f"(now {artifact.reference}, {artifact.status})"
                    )
            elif kind == "preflight":
                self._verify_preflight(task_id, record, aid, verified, mismatches, blocking)
            elif kind == "retry_budget":
                if self._retry_scheduler is None:
                    blocking.append(f"{aid}: no retry scheduler to confirm the cancellation")
                elif self._retry_scheduler.get_retry_schedule(task_id) is not None:
                    mismatches.append(f"cancelled {aid} still has a scheduled retry; it remains executable")
                else:
                    verified.append(aid)
            elif kind in _PRECONDITION_KINDS:
                if self._integrity_service is None:
                    blocking.append(f"{aid}: no integrity service to confirm current preconditions")
                else:
                    integrity = self._integrity_service.check(task_id, current)
                    if integrity.status == INTEGRITY_VALID:
                        verified.append(aid)
                    else:
                        mismatches.append(
                            f"revalidated {aid}: current decision {current} fails its integrity check: "
                            f"{'; '.join(integrity.issues)}"
                        )
            else:
                blocking.append(f"{aid}: no known way to verify a {kind} artifact")

        for label, outcomes in (("skipped", record.skipped), ("failed", record.failed)):
            for outcome in outcomes:
                aid, kind = outcome.artifact_id, outcome.artifact_type
                resolved = (
                    kind in by_kind and by_kind[kind].status == ARTIFACT_FRESH
                    and (kind in _DECISION_REFERENCING or aid not in stale_now)
                )
                if kind in by_kind and resolved:
                    mismatches.append(f"{label} {aid} is no longer stale, but no action was recorded for it")
                else:
                    unresolved.append(aid)
                    blocking.append(f"{aid} ({label}) remains unresolved and blocks execution")

        recorded = set(record.artifact_ids) | set(record.remaining_stale)
        for aid in sorted(stale_now - recorded):
            mismatches.append(f"{aid} became stale outside this operation")
        if set(record.remaining_stale) != stale_now:
            mismatches.append(
                "the audit's remaining stale artifacts do not match current state: recorded "
                f"{sorted(record.remaining_stale)}, now {sorted(stale_now)}"
            )
        if record.post_staleness_status != staleness.status:
            mismatches.append(
                f"the audit recorded staleness {record.post_staleness_status!r}, but it is now {staleness.status!r}"
            )
        return self._result(task_id, invalidation_operation_id, verified, unresolved, mismatches, blocking)

    def _verify_preflight(self, task_id, record, aid, verified, mismatches, blocking):
        if self._preflight_service is None or self._snapshot_service is None:
            blocking.append(f"{aid}: no preflight invalidation or snapshot service to confirm the invalidation")
            return
        previous = self._decision_store.get(record.previous_decision_id)
        snapshot = self._snapshot_service.get(task_id, previous.snapshot_id) if previous is not None else None
        if snapshot is None:
            blocking.append(f"{aid}: the preflight it referenced cannot be established")
        elif self._preflight_service.get_invalidation(snapshot.preflight_id) is None:
            mismatches.append(f"invalidated {aid}: preflight {snapshot.preflight_id} has no recorded invalidation")
        else:
            verified.append(aid)

    @staticmethod
    def _result(task_id, operation_id, verified, unresolved, mismatches, blocking):
        status = (
            IMPACT_INVALIDATION_VERIFICATION_VALID if not mismatches and not blocking
            else IMPACT_INVALIDATION_VERIFICATION_INVALID
        )
        return AgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationResult(
            task_id=task_id, operation_id=operation_id, status=status, verified_artifacts=tuple(verified),
            unresolved_artifacts=tuple(unresolved), mismatches=tuple(mismatches), blocking_issues=tuple(blocking),
        )
