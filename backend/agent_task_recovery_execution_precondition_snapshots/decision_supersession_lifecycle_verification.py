from .decision_supersession_conflict_plan import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService,
)
from .decision_supersession_conflict_resolution_audit import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService,
)
from .decision_supersession_lifecycle_result import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultService,
)
from .decision_supersession_resolution import LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService
from .decision_supersession_resolution_verification import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationService,
)
from .models import (
    CONFLICT_ACTION_APPLIED,
    LIFECYCLE_VERIFICATION_INVALID,
    LIFECYCLE_VERIFICATION_VALID,
    RESOLUTION_RESOLVED,
    SUPERSESSION_LIFECYCLE_CLEAN,
    SUPERSESSION_LIFECYCLE_RESOLVED,
    SUPERSESSION_LIFECYCLE_RESULT_SCHEMA_VERSION,
    AgentTaskRecoveryExecutionDecisionSupersessionLifecycleVerificationResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionSupersessionLifecycleVerificationError(ValueError):
    """Raised when verify() is given invalid arguments."""


class LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleVerificationService:
    """The final end-to-end check of the supersession-resolution chain:
    verifies that a persisted lifecycle result (#12) still accurately
    describes the repository -- read-only and never repairing or rerunning
    resolution. It compares the persisted record with the operation's own
    audit record (#9) and with the post-resolution verification (#10,
    itself built on #2 validation, #3 resolution and #6/#4 planning, with
    optional decision integrity checks).

    A record that claims success without a passing verification, applied
    actions that are not reflected in the chain, skipped or failed
    conflicts that vanished (a stale record), a terminal decision that is
    no longer authoritative, or an audit that disagrees are mismatches;
    records the result depends on that no longer exist are missing
    evidence. Fails closed: when the authoritative lineage cannot be
    established, terminal_decision_id is None.
    """

    def __init__(
        self,
        lifecycle_result_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultService = None,
        audit_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService = None,
        resolution_verification_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationService = None,
        resolution_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService = None,
        plan_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService = None,
    ):
        """All collaborators must share the same stores."""
        self._results = lifecycle_result_service or LLMAgentTaskRecoveryExecutionDecisionSupersessionLifecycleResultService()
        self._audit_service = audit_service or LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionAuditService()
        self._resolution_service = resolution_service or LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService()
        self._plan_service = plan_service or LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService()
        self._verification_service = (
            resolution_verification_service
            or LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionVerificationService(
                audit_service=self._audit_service, resolution_service=self._resolution_service,
                plan_service=self._plan_service,
            )
        )

    def verify(
        self, task_id: str, lifecycle_result_id: str
    ) -> AgentTaskRecoveryExecutionDecisionSupersessionLifecycleVerificationResult:
        """Verify task_id's persisted lifecycle result lifecycle_result_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionSupersessionLifecycleVerificationError:
                If task_id/lifecycle_result_id is not a non-empty string
        """
        for value, name in ((task_id, "task_id"), (lifecycle_result_id, "lifecycle_result_id")):
            if not value or not isinstance(value, str):
                raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionLifecycleVerificationError(
                    f"{name} is required and must be a non-empty string"
                )

        record = self._results.get(task_id, lifecycle_result_id)
        if record is None:
            return self._result(
                task_id, lifecycle_result_id, (),
                (f"lifecycle result {lifecycle_result_id} does not exist for task {task_id}",), (), None,
            )

        mismatches, missing = [], []
        if record.schema_version != SUPERSESSION_LIFECYCLE_RESULT_SCHEMA_VERSION:
            mismatches.append(f"unsupported lifecycle result schema version {record.schema_version!r}")
        if record.state == SUPERSESSION_LIFECYCLE_RESOLVED and (
            record.verification_status != LIFECYCLE_VERIFICATION_VALID or record.remaining_blockers
        ):
            mismatches.append("the lifecycle was recorded as resolved without a passing verification")

        resolution = self._resolution_service.resolve(task_id)
        current_conflicts = tuple(item.conflict_id for item in self._plan_service.plan(task_id).items)

        if record.operation_id is None:
            # No resolution operation ran (clean / validation or execution failure).
            if record.state == SUPERSESSION_LIFECYCLE_CLEAN and current_conflicts:
                mismatches.append(
                    f"the lifecycle was recorded clean, but conflicts now exist: {', '.join(current_conflicts)}"
                )
            blockers = tuple(f"conflict {cid} still blocks execution" for cid in current_conflicts)
            if resolution.resolution_state != RESOLUTION_RESOLVED:
                blockers += (f"the lineage does not resolve ({resolution.resolution_state})",)
            terminal = resolution.terminal_decision_id
        else:
            audit = next(
                (r for r in self._audit_service.list(task_id) if r.operation_id == record.operation_id), None
            )
            if audit is None:
                missing.append(f"no audit record exists for operation {record.operation_id}")
            else:
                if record.audit_id != audit.audit_id:
                    mismatches.append(
                        f"the lifecycle references audit {record.audit_id}, but operation {record.operation_id} "
                        f"was audited as {audit.audit_id}"
                    )
                for label, recorded, audited in (
                    ("applied", record.applied, audit.applied + audit.delegated),
                    ("skipped", record.skipped, audit.skipped),
                    ("failed", record.failed, audit.failed),
                ):
                    if sorted(o.conflict_id for o in recorded) != sorted(o.conflict_id for o in audited):
                        mismatches.append(f"the lifecycle's {label} actions disagree with the audit record")

            verification = self._verification_service.verify(task_id, record.operation_id)
            missing.extend(
                issue for issue in verification.blocking_issues if "has no audit record" in issue
            )
            for outcome in record.applied:
                if outcome.outcome == CONFLICT_ACTION_APPLIED and (
                    outcome.conflict_id not in verification.applied_actions_verified
                ):
                    mismatches.append(
                        f"applied action {outcome.conflict_id} is not reflected in the current supersession chain"
                    )
            for label, outcomes in (("skipped", record.skipped), ("failed", record.failed)):
                for outcome in outcomes:
                    if outcome.conflict_id not in current_conflicts:
                        mismatches.append(
                            f"{label} conflict {outcome.conflict_id} is no longer present; the lifecycle result is stale"
                        )
            mismatches.extend(f"post-resolution lineage: {m}" for m in verification.mismatches)
            blockers = tuple(i for i in verification.blocking_issues if "has no audit record" not in i)
            terminal = verification.terminal_decision_id

        if record.terminal_decision_id is not None and record.terminal_decision_id != terminal:
            mismatches.append(
                f"recorded terminal decision {record.terminal_decision_id} is no longer authoritative "
                f"(now {terminal})"
            )
        return self._result(task_id, lifecycle_result_id, mismatches, missing, blockers, terminal)

    @staticmethod
    def _result(task_id, result_id, mismatches, missing, blockers, terminal):
        status = (
            LIFECYCLE_VERIFICATION_VALID if not mismatches and not missing else LIFECYCLE_VERIFICATION_INVALID
        )
        return AgentTaskRecoveryExecutionDecisionSupersessionLifecycleVerificationResult(
            task_id=task_id, lifecycle_result_id=result_id, status=status, mismatches=tuple(mismatches),
            missing_evidence=tuple(missing), remaining_blockers=tuple(blockers),
            terminal_decision_id=terminal if status == LIFECYCLE_VERIFICATION_VALID else None,
        )
