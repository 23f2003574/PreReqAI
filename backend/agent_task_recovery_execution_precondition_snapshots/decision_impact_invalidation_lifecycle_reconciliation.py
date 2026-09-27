from .models import (
    ARTIFACT_STALE,
    IMPACT_RECONCILIATION_ALREADY_REPLACED,
    IMPACT_RECONCILIATION_FAILED_CLOSED,
    IMPACT_RECONCILIATION_NO_OP,
    IMPACT_RECONCILIATION_REPLACED,
    RESOLUTION_RESOLVED,
    AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationError(ValueError):
    """Raised when reconcile() is given invalid arguments."""


class LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationService:
    """Reconciles a persisted remediation lifecycle result (#9) with
    current decision and artifact state -- detecting whether that
    remediation has become obsolete, and if so running the EXISTING
    remediation lifecycle (#8) again as a new operation rather than any
    remediation logic of its own:

      1. verify the persisted result (#10);
      2. re-resolve the authoritative decision (supersession resolution);
      3. re-check artifact staleness (#1 impact + #2 staleness);
      4-5. if the result is still valid and the decision is unchanged, it
         is a no-op;
      6. otherwise run #8 and persist its result through #9 as the
         replacement, verifying it through #10;
      7. the original result is never modified (the #9 store is
         append-only).

    Every mutation happens inside #8, which never bypasses precondition
    checks or executes recovery. Fails closed when the result, its
    evidence, or the authoritative decision cannot be established.
    Idempotent: a later, still-valid result for the same authoritative
    decision is reported as ALREADY_REPLACED instead of running again.
    """

    def __init__(
        self, lifecycle_result_service, lifecycle_verification_service, lifecycle_service, resolution_service,
        impact_service, staleness_service,
    ):
        """The existing #9, #10 and #8 services, the supersession
        resolution service, and #1/#2 -- all wired to the same stores."""
        self._results = lifecycle_result_service
        self._verification = lifecycle_verification_service
        self._lifecycle = lifecycle_service
        self._resolution = resolution_service
        self._impact = impact_service
        self._staleness = staleness_service

    def reconcile(
        self, task_id: str, lifecycle_result_id: str
    ) -> AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResult:
        """Reconcile task_id's persisted lifecycle result.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationError:
                If task_id/lifecycle_result_id is not a non-empty string
        """
        for value, name in ((task_id, "task_id"), (lifecycle_result_id, "lifecycle_result_id")):
            if not value or not isinstance(value, str):
                raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationError(
                    f"{name} is required and must be a non-empty string"
                )

        record = self._results.get(task_id, lifecycle_result_id)
        verification = self._verification.verify(task_id, lifecycle_result_id)
        if record is None:
            return self._result(task_id, lifecycle_result_id, None, IMPACT_RECONCILIATION_FAILED_CLOSED,
                                issues=verification.missing_evidence)

        resolution = self._resolution.resolve(task_id)
        if resolution.resolution_state != RESOLUTION_RESOLVED:
            return self._result(
                task_id, lifecycle_result_id, record, IMPACT_RECONCILIATION_FAILED_CLOSED,
                issues=(f"the authoritative decision cannot be established ({resolution.resolution_state})",),
            )
        current = resolution.terminal_decision_id
        chain = tuple(resolution.chain)
        newly_stale = ()
        if len(chain) >= 2:
            staleness = self._staleness.check(task_id, self._impact.analyze(task_id, chain[-2], current))
            known = set(record.remaining_stale) | set(record.affected_artifacts)
            newly_stale = tuple(
                f"{a.kind}:{a.reference}" for a in staleness.artifacts
                if a.status == ARTIFACT_STALE and f"{a.kind}:{a.reference}" not in known
            )

        unchanged = current == record.authoritative_decision_id and not newly_stale
        if verification.valid and unchanged:
            return self._result(
                task_id, lifecycle_result_id, record, IMPACT_RECONCILIATION_NO_OP, current=current,
                blockers=verification.remaining_blockers, final=verification.status,
            )
        if verification.missing_evidence and unchanged:
            return self._result(
                task_id, lifecycle_result_id, record, IMPACT_RECONCILIATION_FAILED_CLOSED, current=current,
                issues=verification.missing_evidence,
            )

        latest = self._results.latest(task_id)
        if latest is not None and latest.result_id != lifecycle_result_id and latest.authoritative_decision_id == current:
            latest_verification = self._verification.verify(task_id, latest.result_id)
            if latest_verification.valid:
                return self._result(
                    task_id, lifecycle_result_id, record, IMPACT_RECONCILIATION_ALREADY_REPLACED, current=current,
                    newly_stale=newly_stale, replacement=latest, blockers=latest_verification.remaining_blockers,
                    final=latest_verification.status,
                )

        replacement = self._results.record(task_id, self._lifecycle.run(task_id))
        replacement_verification = self._verification.verify(task_id, replacement.result_id)
        return self._result(
            task_id, lifecycle_result_id, record, IMPACT_RECONCILIATION_REPLACED, current=current,
            newly_stale=newly_stale, replacement=replacement,
            blockers=tuple(replacement_verification.remaining_blockers) + tuple(replacement_verification.mismatches),
            final=replacement_verification.status, issues=tuple(verification.mismatches),
        )

    @staticmethod
    def _result(task_id, result_id, record, state, current=None, newly_stale=(), replacement=None, blockers=(),
                final=None, issues=()):
        return AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationResult(
            task_id=task_id, previous_result_id=result_id,
            previous_status=record.status if record is not None else None, state=state, current_decision_id=current,
            newly_stale_artifacts=tuple(newly_stale),
            replacement_result_id=replacement.result_id if replacement is not None else None,
            replacement_operation_id=replacement.operation_id if replacement is not None else None,
            unresolved_blockers=tuple(blockers), final_verification_status=final, issues=tuple(issues),
        )
