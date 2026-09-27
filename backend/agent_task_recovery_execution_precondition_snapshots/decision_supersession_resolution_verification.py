from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .decision_supersession_conflict_plan import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService,
)
from .decision_supersession_conflict_resolution_audit import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService,
)
from .decision_supersession_resolution import LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService
from .decision_supersession_validation import LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService
from .models import (
    CONFLICT_RESOLUTION_AUDIT_SCHEMA_VERSION,
    EXECUTION_DECISION_ALLOW,
    INTEGRITY_VALID,
    PLAN_REPAIRABLE_METADATA,
    PLAN_REQUIRES_REVALIDATION,
    RESOLUTION_RESOLVED,
    RESOLUTION_VERIFICATION_INVALID,
    RESOLUTION_VERIFICATION_VALID,
    SUPERSESSION_CONFLICT_CYCLE,
    SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS,
    AgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationResult,
)

_INTRODUCIBLE = (SUPERSESSION_CONFLICT_CYCLE, SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS)


class InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationError(ValueError):
    """Raised when verify() is given invalid arguments."""


class LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationService:
    """Verifies, after the fact, that a conflict-resolution operation (#8)
    left a valid, safe decision lineage -- a read-only comparison of the
    operation's own audit record (#9) with the currently persisted state,
    as seen through the existing supersession validation (#2), resolution
    (#3) and conflict planning (#6/#4) services, plus (optionally) the
    decision integrity check. It never repairs anything.

    Fails closed: a missing operation or a lineage that no longer resolves
    leaves terminal_decision_id None and the verdict INVALID.
    """

    def __init__(
        self,
        audit_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService = None,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        supersession_validation_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService = None,
        resolution_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService = None,
        plan_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService = None,
        integrity_service=None,
    ):
        """All collaborators must share the same stores."""
        self._audit_service = (
            audit_service if audit_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService()
        )
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._validation_service = (
            supersession_validation_service if supersession_validation_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(decision_store=self._decision_store)
        )
        self._resolution_service = (
            resolution_service if resolution_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService(decision_store=self._decision_store)
        )
        self._plan_service = (
            plan_service if plan_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService()
        )
        self._integrity_service = integrity_service

    def verify(
        self, task_id: str, resolution_operation_id: str
    ) -> AgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationResult:
        """Verify task_id's resolution operation resolution_operation_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationError:
                If task_id/resolution_operation_id is not a non-empty string
        """
        for value, name in ((task_id, "task_id"), (resolution_operation_id, "resolution_operation_id")):
            if not value or not isinstance(value, str):
                raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationError(
                    f"{name} is required and must be a non-empty string"
                )

        record = next(
            (r for r in self._audit_service.list(task_id) if r.operation_id == resolution_operation_id), None
        )
        if record is None:
            return self._result(
                task_id, resolution_operation_id, (), (), (),
                (f"resolution operation {resolution_operation_id} has no audit record for task {task_id}",), None,
            )

        mismatches, blocking = [], []
        if record.schema_version != CONFLICT_RESOLUTION_AUDIT_SCHEMA_VERSION:
            mismatches.append(f"unsupported audit schema version {record.schema_version!r}")

        validation = self._validation_service.validate(task_id)
        resolution = self._resolution_service.resolve(task_id)
        current = self._plan_service.plan(task_id)
        current_ids = tuple(item.conflict_id for item in current.items)
        current_by_id = {item.conflict_id: item for item in current.items}

        verified = []
        for outcome in record.applied:
            if outcome.classification != PLAN_REPAIRABLE_METADATA:
                mismatches.append(
                    f"applied action {outcome.conflict_id} is a {outcome.classification} item, which a validated "
                    "plan never lets execution apply"
                )
            elif outcome.conflict_id in current_by_id:
                mismatches.append(f"applied action {outcome.conflict_id} did not take effect: the conflict persists")
            else:
                verified.append(outcome.conflict_id)
        for outcome in record.delegated:
            if outcome.classification != PLAN_REQUIRES_REVALIDATION:
                mismatches.append(
                    f"delegated action {outcome.conflict_id} is a {outcome.classification} item, not a revalidation"
                )

        for item in current.items:
            if item.conflict_type in _INTRODUCIBLE and item.conflict_id not in record.conflict_ids:
                mismatches.append(f"{item.conflict_type} conflict {item.conflict_id} was introduced after the operation")

        involved = []
        for outcome in record.applied + record.delegated + record.skipped + record.failed:
            for decision_id in outcome.decision_ids:
                if decision_id not in involved:
                    involved.append(decision_id)
        for decision_id in involved:
            decision = self._decision_store.get(decision_id)
            if decision is None:
                continue  # a missing-decision conflict is reported through remaining conflicts
            if decision.task_id != task_id:
                continue
            if self._integrity_service is not None:
                integrity = self._integrity_service.check(task_id, decision_id)
                if integrity.status != INTEGRITY_VALID:
                    mismatches.append(
                        f"decision {decision_id} failed its integrity check after the operation: "
                        f"{'; '.join(integrity.issues)}"
                    )
        for issue in validation.issues:
            if "verdict" in issue and "disagrees" in issue:
                mismatches.append(f"forbidden decision mutation: {issue}")

        if record.post_chain_status != validation.status:
            mismatches.append(
                f"audit recorded chain status {record.post_chain_status!r}, but it is now {validation.status!r}"
            )
        if record.post_terminal_decision_id != validation.terminal_decision_id:
            mismatches.append(
                f"audit recorded terminal decision {record.post_terminal_decision_id}, but the lineage now ends at "
                f"{validation.terminal_decision_id}"
            )
        if set(record.still_blocking) != set(current_ids):
            mismatches.append(
                "audit's remaining blocking conflicts do not match the current conflicts: recorded "
                f"{sorted(record.still_blocking)}, now {sorted(current_ids)}"
            )

        for item in current.items:
            blocking.append(f"conflict {item.conflict_id} ({item.classification}) still blocks execution")
        terminal = None
        if resolution.resolution_state != RESOLUTION_RESOLVED:
            blocking.append(f"the lineage does not resolve ({resolution.resolution_state}); execution stays blocked")
        else:
            terminal = resolution.terminal_decision_id
            if resolution.terminal_decision != EXECUTION_DECISION_ALLOW:
                blocking.append(
                    f"terminal decision {terminal} is {resolution.terminal_decision!r}; that condition is preserved "
                    "and execution stays gated"
                )

        return self._result(task_id, resolution_operation_id, verified, current_ids, mismatches, blocking, terminal)

    @staticmethod
    def _result(task_id, operation_id, verified, remaining, mismatches, blocking, terminal):
        status = (
            RESOLUTION_VERIFICATION_VALID if not mismatches and not blocking else RESOLUTION_VERIFICATION_INVALID
        )
        return AgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationResult(
            task_id=task_id, operation_id=operation_id, status=status,
            applied_actions_verified=tuple(verified), remaining_conflicts=tuple(remaining),
            mismatches=tuple(mismatches), blocking_issues=tuple(blocking), terminal_decision_id=terminal,
        )
