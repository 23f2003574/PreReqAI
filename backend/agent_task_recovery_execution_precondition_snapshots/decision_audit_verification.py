from datetime import datetime, timezone

from .decision_audit import LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import AgentTaskRecoveryExecutionPreconditionDecisionAuditVerification

_REQUIRED_TEXT_FIELDS = ("decision", "snapshot_id", "reason")


class InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationError(ValueError):
    """Raised when verify() is given invalid arguments, or audit_id names
    no audit record recorded for task_id."""


class LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationService:
    """Verifies that a Commit #12 audit record still faithfully represents
    the Commit #7-persisted decision it references -- never a second
    audit/persistence system (Rule: "Do not create another audit or
    persistence system"): verify() only ever reads through Commit #12's
    own audit store (get()) and Commit #7's own decision store (get()),
    and compares their already-persisted fields -- it never calls
    validate()/classify()/reconcile()/decide() or record() itself.

    No existing hash/signature mechanism applies here (Rule: "Reuse
    existing integrity/hash/version mechanisms if the repository already
    has them," checked and found inapplicable): Commit #12's own audit
    record carries no hash/signature field at all (unlike backend.
    agent_task_recovery_preflight_dependency_snapshots' own integrity/
    signing records, a genuinely different domain with its own hashed
    baseline) -- a plain field-by-field comparison against the decision
    it references is the correct, minimal mechanism for this record
    shape, not a second, invented hashing scheme.

    Fails closed when the referenced decision cannot be found (Rule):
    decision_found=False always forces valid=False, regardless of
    whether the audit's own fields look otherwise well-formed.

    Never repairs or mutates anything (Rule: "Never repair or mutate the
    audit automatically") -- read-only throughout.

    Deterministic (Rule): both underlying stores are already
    deterministic reads, so calling verify() twice in a row with nothing
    else changed always returns an identical result.
    """

    def __init__(
        self,
        audit_service: LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService = None,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
    ):
        """
        Args:
            audit_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService;
                pass the real instance holding the audit entries record()
                actually persisted.
            decision_store: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionStore;
                pass the real instance holding the decisions decide()
                actually persisted.
        """
        self._audit_service = (
            audit_service
            if audit_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionDecisionAuditService()
        )
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )

    def verify(self, task_id: str, audit_id: str) -> AgentTaskRecoveryExecutionPreconditionDecisionAuditVerification:
        """Verify task_id's exact, already-recorded audit_id still
        faithfully represents its referenced decision.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationError:
                If task_id/audit_id is not a non-empty string, or
                audit_id names no audit record recorded for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(audit_id, "audit_id")

        audit = self._audit_service.get(audit_id)
        if audit is None or audit.task_id != task_id:
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationError(
                f"no audit record {audit_id!r} is recorded for task_id {task_id!r}"
            )

        missing_fields = tuple(
            field_name for field_name in _REQUIRED_TEXT_FIELDS if not getattr(audit, field_name)
        )

        decision = self._decision_store.get(audit.decision_id)
        if decision is None:
            return AgentTaskRecoveryExecutionPreconditionDecisionAuditVerification(
                task_id=task_id, audit_id=audit_id, decision_id=audit.decision_id,
                decision_found=False, valid=False, mismatches=(), missing_fields=missing_fields,
                reason=f"the referenced decision {audit.decision_id!r} no longer exists in the decision store",
                verified_at=self._now(),
            )

        mismatches = []
        for field_name in (
            "task_id", "snapshot_id", "authorization_id", "decision", "reason", "blocking_conditions", "warnings",
        ):
            if getattr(audit, field_name) != getattr(decision, field_name):
                mismatches.append(field_name)
        mismatches = tuple(mismatches)

        valid = not mismatches and not missing_fields
        reason = None
        if not valid:
            reasons = []
            if mismatches:
                reasons.append(f"audit no longer matches the decision on: {', '.join(mismatches)}")
            if missing_fields:
                reasons.append(f"required audit fields are missing: {', '.join(missing_fields)}")
            reason = "; ".join(reasons)

        return AgentTaskRecoveryExecutionPreconditionDecisionAuditVerification(
            task_id=task_id, audit_id=audit_id, decision_id=audit.decision_id,
            decision_found=True, valid=valid, mismatches=mismatches, missing_fields=missing_fields,
            reason=reason, verified_at=self._now(),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionAuditVerificationError(
                f"{field_name} is required and must be a non-empty string"
            )
