from .decision_freshness_audit import LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService
from .decision_freshness_chain_reconciliation import (
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
)
from .decision_freshness_chain_repair import InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .decision_supersession import InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore
from .decision_supersession_conflict import LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService
from .decision_supersession_conflict_plan import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService,
)
from .decision_supersession_conflict_plan_validation import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationService,
)
from .decision_supersession_conflict_resolution import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionService,
)
from .decision_supersession_conflict_resolution_audit import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService,
)
from .decision_supersession_resolution import LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService
from .decision_supersession_resolution_verification import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationService,
)
from .decision_supersession_validation import LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService
from .models import (
    EXECUTION_DECISION_ALLOW,
    RESOLUTION_RESOLVED,
    SUPERSESSION_LIFECYCLE_BLOCKED,
    SUPERSESSION_LIFECYCLE_CLEAN,
    SUPERSESSION_LIFECYCLE_EXECUTION_FAILED,
    SUPERSESSION_LIFECYCLE_RESOLVED,
    SUPERSESSION_LIFECYCLE_UNSAFE,
    SUPERSESSION_LIFECYCLE_VALIDATION_FAILED,
    AgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleError(ValueError):
    """Raised when resolve() is given an invalid task_id."""


class LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleService:
    """One orchestration boundary for the supersession conflict-resolution
    lifecycle: detect (#4) -> plan (#6) -> validate (#7) -> execute only
    safe actions (#8) -> audit (#9) -> verify (#10). Every step is
    delegated; this class only sequences them and consolidates the
    outcome.

    Validation is never bypassed (a rejected plan is not executed, and #8
    re-validates anyway); review/block is never promoted (only #8's
    reconciliation-backed pointer repair mutates anything); history and
    audit records are only appended to. A failed or mismatching
    verification is reported UNSAFE, never success. Idempotent when no
    conflict remains: a clean task runs no execution and writes no audit.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        supersession_store=None,
        freshness_audit_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService = None,
        chain_index_store=None,
        revalidation_service=None,
        conflict_service=None,
        resolution_service=None,
        plan_service=None,
        plan_validation_service=None,
        execution_service=None,
        audit_service=None,
        verification_service=None,
    ):
        """Collaborators default to one stack wired to the SAME
        decision_store/supersession_store/freshness_audit_service/
        chain_index_store; revalidation_service is forwarded to execution
        (see #8)."""
        decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        supersession_store = (
            supersession_store if supersession_store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
        )
        freshness_audit_service = (
            freshness_audit_service if freshness_audit_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()
        )
        chain_index_store = (
            chain_index_store if chain_index_store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionFreshnessChainIndexStore()
        )
        common = dict(
            decision_store=decision_store, freshness_audit_service=freshness_audit_service,
            chain_index_store=chain_index_store,
        )
        self._resolution_service = resolution_service or LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService(
            supersession_store=supersession_store, **common
        )
        self._conflict_service = conflict_service or LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService(
            supersession_store=supersession_store, resolution_service=self._resolution_service, **common
        )
        self._plan_service = plan_service or LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService(
            conflict_service=self._conflict_service, resolution_service=self._resolution_service,
        )
        self._plan_validation_service = (
            plan_validation_service
            or LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationService(
                plan_service=self._plan_service, decision_store=decision_store,
                supersession_store=supersession_store, freshness_audit_service=freshness_audit_service,
            )
        )
        supersession_validation = LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
            supersession_store=supersession_store, **common
        )
        self._execution_service = execution_service or LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionService(
            plan_service=self._plan_service, plan_validation_service=self._plan_validation_service,
            reconciliation_service=LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService(**common),
            revalidation_service=revalidation_service, supersession_validation_service=supersession_validation,
        )
        self._audit_service = audit_service or LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService()
        self._verification_service = (
            verification_service
            or LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationService(
                audit_service=self._audit_service, decision_store=decision_store,
                supersession_validation_service=supersession_validation,
                resolution_service=self._resolution_service, plan_service=self._plan_service,
            )
        )

    def resolve(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleResult:
        """Run the conflict-resolution lifecycle for task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleError(
                "task_id is required and must be a non-empty string"
            )

        detection = self._conflict_service.detect(task_id)
        if not detection.has_conflicts:
            resolution = self._resolution_service.resolve(task_id)
            blockers = []
            terminal = None
            if resolution.resolution_state != RESOLUTION_RESOLVED:
                blockers.append(f"the lineage does not resolve ({resolution.resolution_state})")
                blockers.extend(resolution.issues)
            else:
                terminal = resolution.terminal_decision_id
                if resolution.terminal_decision != EXECUTION_DECISION_ALLOW:
                    blockers.append(f"terminal decision {terminal} is {resolution.terminal_decision!r}")
            state = (
                SUPERSESSION_LIFECYCLE_CLEAN if resolution.resolution_state == RESOLUTION_RESOLVED
                else SUPERSESSION_LIFECYCLE_BLOCKED
            )
            return self._result(task_id, state, detection=detection, blockers=blockers, terminal=terminal)

        plan = self._plan_service.plan(task_id)
        plan_validation = self._plan_validation_service.validate(task_id, plan)
        if not plan_validation.valid:
            return self._result(
                task_id, SUPERSESSION_LIFECYCLE_VALIDATION_FAILED, detection=detection, plan=plan,
                plan_validation=plan_validation, blockers=plan_validation.issues,
            )

        errors = []
        try:
            execution = self._execution_service.execute(task_id, plan)
        except Exception as error:
            return self._result(
                task_id, SUPERSESSION_LIFECYCLE_EXECUTION_FAILED, detection=detection, plan=plan,
                plan_validation=plan_validation, errors=(f"execution failed: {type(error).__name__}: {error}",),
                blockers=tuple(item.conflict_id for item in plan.items),
            )
        audit = None
        try:
            audit = self._audit_service.record(task_id, execution)
        except Exception as error:
            errors.append(f"recording the resolution audit failed: {type(error).__name__}: {error}")

        verification = None
        if audit is not None:
            try:
                verification = self._verification_service.verify(task_id, execution.operation_id)
            except Exception as error:
                errors.append(f"verification failed: {type(error).__name__}: {error}")

        if errors and audit is None:
            state = SUPERSESSION_LIFECYCLE_EXECUTION_FAILED
        elif verification is None or verification.mismatches:
            state = SUPERSESSION_LIFECYCLE_UNSAFE
        elif verification.blocking_issues:
            state = SUPERSESSION_LIFECYCLE_BLOCKED
        else:
            state = SUPERSESSION_LIFECYCLE_RESOLVED
        blockers = tuple(verification.blocking_issues) + tuple(verification.mismatches) if verification else tuple(
            execution.still_blocking
        )
        return self._result(
            task_id, state, detection=detection, plan=plan, plan_validation=plan_validation, execution=execution,
            audit=audit, verification=verification, blockers=blockers,
            terminal=verification.terminal_decision_id if verification is not None else None, errors=tuple(errors),
        )

    @staticmethod
    def _result(
        task_id, state, detection=None, plan=None, plan_validation=None, execution=None, audit=None,
        verification=None, blockers=(), terminal=None, errors=(),
    ):
        applied = tuple(execution.applied) if execution is not None else ()
        return AgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleResult(
            task_id=task_id, state=state,
            partial=state == SUPERSESSION_LIFECYCLE_BLOCKED and bool(applied),
            operation_id=execution.operation_id if execution is not None else None,
            conflicts=tuple(detection.conflicts) if detection is not None else (),
            planned_actions=tuple(plan.items) if plan is not None else (),
            applied=applied, skipped=tuple(execution.skipped) if execution is not None else (),
            failed=tuple(execution.failed) if execution is not None else (),
            remaining_blockers=tuple(blockers), terminal_decision_id=terminal, plan_validation=plan_validation,
            audit_id=audit.audit_id if audit is not None else None, verification=verification, errors=tuple(errors),
        )
