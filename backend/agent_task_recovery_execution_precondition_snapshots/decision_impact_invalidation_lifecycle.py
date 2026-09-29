from datetime import datetime, timezone

from .models import (
    ARTIFACT_FRESH,
    ARTIFACT_STALE,
    IMPACT_LIFECYCLE_BLOCKED,
    IMPACT_LIFECYCLE_CLEAN,
    IMPACT_LIFECYCLE_EXECUTION_FAILED,
    IMPACT_LIFECYCLE_REMEDIATED,
    IMPACT_LIFECYCLE_UNRESOLVED,
    IMPACT_LIFECYCLE_UNSAFE,
    IMPACT_LIFECYCLE_UP_TO_DATE,
    IMPACT_LIFECYCLE_VALIDATION_FAILED,
    INVALIDATION_MANUAL_REVIEW,
    RESOLUTION_RESOLVED,
    AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleError(ValueError):
    """Raised when run() is given an invalid task_id."""


class LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleService:
    """Orchestrates the downstream-artifact remediation flow built in
    #1-#7: resolve the authoritative decision (supersession resolution)
    -> change impact (#1) -> staleness (#2) -> plan (#3) -> validate (#4)
    -> execute safe remediation (#5) -> audit (#6) -> verify (#7). Every
    step is delegated; this class only sequences them and consolidates the
    outcome. remaining_stale may still list areas where the two decisions'
    own snapshots inherently differ; success is judged by #7's verification
    of the remediation, not by those. It never runs recovery itself, and every mutation goes
    through #5's existing mechanisms (which never bypass authorization or
    precondition checks).

    The decision change is from the authoritative decision's lineage
    predecessor to the authoritative decision. manual_review items stay
    blocking; a failed or mismatching verification is reported UNSAFE,
    never success. Idempotent: when every actionable step for the same
    decision change was already applied by an earlier audited operation
    whose verification shows no mismatch, nothing runs (UP_TO_DATE).
    """

    def __init__(
        self,
        resolution_service,
        impact_service,
        staleness_service,
        plan_service,
        plan_validation_service,
        execution_service,
        audit_service,
        verification_service,
    ):
        """All collaborators are the existing services from #1-#7 and the
        supersession resolution service, wired to the same stores."""
        self._resolution = resolution_service
        self._impact = impact_service
        self._staleness = staleness_service
        self._planner = plan_service
        self._validation = plan_validation_service
        self._execution = execution_service
        self._audit = audit_service
        self._verification = verification_service

    def run(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResult:
        """Run the impact-invalidation lifecycle for task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleError(
                "task_id is required and must be a non-empty string"
            )

        resolution = self._resolution.resolve(task_id)
        if resolution.resolution_state != RESOLUTION_RESOLVED:
            return self._result(
                task_id, IMPACT_LIFECYCLE_UNRESOLVED,
                errors=(f"no authoritative decision ({resolution.resolution_state})",),
            )
        current = resolution.terminal_decision_id
        chain = tuple(resolution.chain)
        previous = chain[-2] if len(chain) >= 2 else None
        if previous is None:
            return self._result(task_id, IMPACT_LIFECYCLE_CLEAN, current=current)

        impact = self._impact.analyze(task_id, previous, current)
        staleness = self._staleness.check(task_id, impact)
        affected = tuple(f"{a.kind}:{a.reference}" for a in staleness.artifacts if a.status != ARTIFACT_FRESH)
        plan = self._planner.plan(task_id, staleness)
        common = dict(current=current, previous=previous, affected=affected, plan=plan)
        if not plan.items:
            return self._result(task_id, IMPACT_LIFECYCLE_CLEAN, **common)

        actionable = {i.artifact_id for i in plan.items if i.action != INVALIDATION_MANUAL_REVIEW}
        if actionable and actionable <= self._already_applied(task_id, previous, current):
            return self._result(
                task_id, IMPACT_LIFECYCLE_UP_TO_DATE, stale=self._stale(staleness),
                blocking=tuple(i.artifact_id for i in plan.items if i.execution_blocked), **common,
            )

        validation = self._validation.validate(task_id, plan)
        if not validation.valid:
            return self._result(
                task_id, IMPACT_LIFECYCLE_VALIDATION_FAILED, errors=tuple(validation.issues),
                blocking=tuple(validation.blocking_actions), **common,
            )

        try:
            execution = self._execution.execute(task_id, plan)
        except Exception as error:
            return self._result(
                task_id, IMPACT_LIFECYCLE_EXECUTION_FAILED,
                errors=(f"execution failed: {type(error).__name__}: {error}",),
                blocking=tuple(i.artifact_id for i in plan.items), **common,
            )
        errors, audit, verification = [], None, None
        try:
            audit = self._audit.record(task_id, execution)
        except Exception as error:
            errors.append(f"recording the audit failed: {type(error).__name__}: {error}")
        if audit is not None:
            try:
                verification = self._verification.verify(task_id, execution.operation_id)
            except Exception as error:
                errors.append(f"verification failed: {type(error).__name__}: {error}")

        if audit is None:
            status = IMPACT_LIFECYCLE_EXECUTION_FAILED
        elif verification is None or verification.mismatches:
            status = IMPACT_LIFECYCLE_UNSAFE
        elif verification.blocking_issues:
            status = IMPACT_LIFECYCLE_BLOCKED
        else:
            status = IMPACT_LIFECYCLE_REMEDIATED
        return self._result(
            task_id, status, execution=execution, audit=audit, verification=verification,
            stale=self._stale(execution.final_staleness), blocking=tuple(execution.still_blocking),
            errors=tuple(errors), **common,
        )

    def _already_applied(self, task_id, previous, current):
        applied = set()
        for record in self._audit.list(task_id):
            if (record.previous_decision_id, record.current_decision_id) != (previous, current):
                continue
            verification = self._verification.verify(task_id, record.operation_id)
            if not verification.mismatches:
                applied |= {o.artifact_id for o in record.applied}
        return applied

    @staticmethod
    def _stale(staleness):
        if staleness is None:
            return ()
        return tuple(f"{a.kind}:{a.reference}" for a in staleness.artifacts if a.status == ARTIFACT_STALE)

    @staticmethod
    def _result(
        task_id, status, current=None, previous=None, affected=(), plan=None, execution=None, audit=None,
        verification=None, stale=(), blocking=(), errors=(),
    ):
        return AgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResult(
            task_id=task_id, status=status, operation_id=execution.operation_id if execution else None,
            authoritative_decision_id=current, previous_decision_id=previous, affected_artifacts=tuple(affected),
            planned_actions=tuple(plan.items) if plan is not None else (),
            applied=tuple(execution.applied) if execution else (), skipped=tuple(execution.skipped) if execution else (),
            failed=tuple(execution.failed) if execution else (), remaining_stale=tuple(stale),
            blocking_artifacts=tuple(blocking), audit_id=audit.audit_id if audit is not None else None,
            verification=verification, errors=tuple(errors), completed_at=datetime.now(timezone.utc),
        )
