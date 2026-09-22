from datetime import datetime, timezone

from backend.agent_task_recovery_guardrails import LLMAgentTaskRecoveryPreflightAuthorizationService

from .decision_audit import LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService
from .decision_audit_verification import LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationService
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import (
    EXECUTION_DECISIONS,
    INTEGRITY_INVALID,
    INTEGRITY_VALID,
    AgentTaskRecoveryExecutionDecisionIntegrityResult,
)
from .service import LLMAgentTaskRecoveryExecutionPreconditionSnapshotService

_REQUIRED_TEXT_FIELDS = ("task_id", "snapshot_id", "reason")
_REQUIRED_TUPLE_FIELDS = ("blocking_conditions", "warnings")


class InvalidAgentTaskRecoveryExecutionDecisionIntegrityError(ValueError):
    """Raised when check() is given invalid arguments."""


class LLMAgentTaskRecoveryExecutionDecisionIntegrityService:
    """A lightweight, read-only integrity check over one Commit #7-
    persisted decision -- never a second persistence/audit framework
    (Rule: "Do not create another persistence or audit framework"):
    check() only ever reads through Commit #7's own decision store,
    Commit #1's own snapshot service, backend.agent_task_recovery_guardrails'
    own authorization service, and Commit #12/#13's own audit service/
    verification -- it never calls validate()/classify()/reconcile()/
    decide()/record() itself (Rule: "Do not recompute the decision").

    Fails closed on missing critical evidence (Rule): a decision_id that
    does not exist, or belongs to a different task_id, short-circuits to
    INTEGRITY_INVALID immediately -- every other check is skipped since
    there is nothing left to check against.

    No persisted decision carries a version/schema field of its own
    (checked: Commit #7's AgentTaskRecoveryExecutionPreconditionDecision
    has none) -- "persisted decision version/schema is supported"
    degenerates to a structural completeness check (required text fields
    non-blank, required tuple fields actually tuples) rather than a
    version-number comparison that has nothing to compare against.

    Never repairs anything (Rule: "Do not repair records automatically")
    -- every collaborator here is called through its own read-only
    method only.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        snapshot_service: LLMAgentTaskRecoveryExecutionPreconditionSnapshotService = None,
        authorization_service: LLMAgentTaskRecoveryPreflightAuthorizationService = None,
        audit_service: LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService = None,
        audit_verification_service: LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationService = None,
    ):
        """
        Args:
            decision_store: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionStore.
            snapshot_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionSnapshotService;
                pass the real instance holding the snapshot capture()
                actually produced, so referenced-snapshot existence can
                be checked against real data.
            authorization_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightAuthorizationService; pass
                the real instance holding a task's actual authorizations.
            audit_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService.
            audit_verification_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationService.
        """
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._snapshot_service = (
            snapshot_service
            if snapshot_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionSnapshotService()
        )
        self._authorization_service = (
            authorization_service
            if authorization_service is not None
            else LLMAgentTaskRecoveryPreflightAuthorizationService()
        )
        self._audit_service = (
            audit_service
            if audit_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService()
        )
        self._audit_verification_service = (
            audit_verification_service
            if audit_verification_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationService(
                audit_service=self._audit_service, decision_store=self._decision_store
            )
        )

    def check(self, task_id: str, decision_id: str) -> AgentTaskRecoveryExecutionDecisionIntegrityResult:
        """Check task_id's exact decision_id for internal integrity.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionIntegrityError: If
                task_id/decision_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(decision_id, "decision_id")

        decision = self._decision_store.get(decision_id)
        if decision is None or decision.task_id != task_id:
            return self._result(
                task_id, decision_id, (f"no decision {decision_id!r} is recorded for task_id {task_id!r}",)
            )

        issues = []

        if decision.decision not in EXECUTION_DECISIONS:
            issues.append(f"decision state {decision.decision!r} is not a supported value")

        for field_name in _REQUIRED_TEXT_FIELDS:
            if not getattr(decision, field_name):
                issues.append(f"required decision field {field_name!r} is missing/blank")

        for field_name in _REQUIRED_TUPLE_FIELDS:
            if not isinstance(getattr(decision, field_name), tuple):
                issues.append(f"decision field {field_name!r} has an unsupported/malformed type")

        if decision.snapshot_id and self._snapshot_service.get(task_id, decision.snapshot_id) is None:
            issues.append(f"referenced snapshot {decision.snapshot_id!r} does not exist")

        if decision.authorization_id is not None:
            if self._authorization_service.get(task_id, decision.authorization_id) is None:
                issues.append(f"referenced authorization {decision.authorization_id!r} does not exist")

        for audit in self._audit_service.list(task_id):
            if audit.decision_id != decision_id:
                continue
            try:
                verification = self._audit_verification_service.verify(task_id, audit.audit_id)
            except ValueError as error:
                issues.append(f"audit record {audit.audit_id!r} could not be verified: {error}")
                continue
            if not verification.valid:
                issues.append(
                    f"audit record {audit.audit_id!r} is no longer consistent with this decision: "
                    f"{verification.reason}"
                )

        return self._result(task_id, decision_id, tuple(issues))

    def _result(self, task_id: str, decision_id: str, issues: tuple) -> AgentTaskRecoveryExecutionDecisionIntegrityResult:
        return AgentTaskRecoveryExecutionDecisionIntegrityResult(
            task_id=task_id, decision_id=decision_id,
            status=INTEGRITY_VALID if not issues else INTEGRITY_INVALID,
            issues=tuple(issues), checked_at=self._now(),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionIntegrityError(
                f"{field_name} is required and must be a non-empty string"
            )
