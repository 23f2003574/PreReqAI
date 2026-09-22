from datetime import datetime, timezone
from typing import Optional

from .approval_reconciliation import LLMAgentTaskRecoveryExecutionPreconditionApprovalReconciliationService
from .drift import DRIFT_REQUIRES_REVALIDATION
from .models import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    RECONCILED_PRESERVED,
    AgentTaskRecoveryExecutionPreconditionDecision,
)
from .service import LLMAgentTaskRecoveryExecutionPreconditionSnapshotService


class InvalidAgentTaskRecoveryExecutionPreconditionDecisionError(ValueError):
    """Raised when decide()/is_allowed() is given invalid arguments (a
    blank task_id/snapshot_id, or a non-string authorization_id). A
    well-formed but unresolvable snapshot_id is NOT raised here -- it is
    reported as a BLOCK decision instead (Rule: "Fail closed if required
    evidence is unavailable")."""


class LLMAgentTaskRecoveryExecutionPreconditionDecisionService:
    """The one canonical decision point for whether a recovery execution
    may proceed, composing Commit #2 (validation), #3 (drift), #4
    (revalidation), and #5 (approval reconciliation) -- never a second
    precondition engine (Rule: "Do not invent new infrastructure or
    duplicate their rules"): decide() calls Commit #5's own reconcile()
    exactly once (itself calling Commit #4's own revalidate(), itself
    calling Commit #3's own classify(), itself calling Commit #2's own
    validate()) and derives EXECUTION_DECISION_ALLOW/REVIEW/BLOCK purely
    from that one call's own already-computed fields; it never re-runs a
    guard, policy, dependency, retry-budget, or authorization check
    itself.

    Decides off the CURRENT state, never the stale original snapshot in
    isolation: every field this class inspects comes from
    `reconciliation.revalidation.new_drift` -- Commit #4's own drift
    classification of whatever snapshot is CURRENTLY authoritative (the
    original one when nothing needed rebuilding, or a freshly rebuilt one
    otherwise), never `snapshot_id`'s own original drift taken alone. This
    distinction is what correctly resolves "authorization revoked, but a
    valid replacement already exists" to REVIEW rather than BLOCK: the
    ORIGINAL snapshot's own validation is naturally invalid once its
    authorization is revoked, but that alone must not be conflated with
    "genuinely unsafe to execute right now."

    Decision rules, most-severe-first (Rule: "Produce a single
    deterministic decision"):
      BLOCK  -- new_drift is None (Commit #4 could not resolve any active
                authorization to evaluate at all), or new_drift.
                execution_may_continue is False (the current/rebuilt state
                is itself genuinely still blocked) (Rule: "invalid/unsafe
                precondition -> block"; "Fail closed if required evidence
                is unavailable"), or any required evidence could not even
                be computed at all (missing snapshot, a mismatched
                authorization_id, or a composed service raised).
      REVIEW -- new_drift.category is DRIFT_REQUIRES_REVALIDATION (Rule:
                "material drift requiring human review -> review"), or
                reconciliation.state is not RECONCILED_PRESERVED (Rule:
                "approval no longer applicable -> review" -- Commit #5's
                own RECONCILED_REQUIRES_REVIEW).
      ALLOW  -- only when none of the above apply (Rule: "valid snapshot +
                applicable approval + no blocking drift -> allow").

    Never executes, authorizes, schedules, or approves anything (Rule:
    "Never execute recovery from this service; it is the canonical
    decision boundary only") -- every call here is read-only.

    Deterministic by composition (Rule): every composed service is
    already deterministic/idempotent over its own fixed input, so calling
    decide() twice in a row with nothing else changed always returns an
    identical decision/reason.
    """

    def __init__(
        self,
        snapshot_service: LLMAgentTaskRecoveryExecutionPreconditionSnapshotService = None,
        approval_reconciliation_service: LLMAgentTaskRecoveryExecutionPreconditionApprovalReconciliationService = None,
    ):
        """
        Args:
            snapshot_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionSnapshotService;
                pass the real instance holding the snapshot capture()
                actually produced.
            approval_reconciliation_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionApprovalReconciliationService
                (itself composing Commits #2-#4); pass the real instance
                wired to the same guard/authorization/approval stack.
        """
        self._snapshot_service = (
            snapshot_service
            if snapshot_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionSnapshotService()
        )
        self._approval_reconciliation_service = (
            approval_reconciliation_service
            if approval_reconciliation_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionApprovalReconciliationService()
        )

    def decide(
        self, task_id: str, snapshot_id: str, authorization_id: Optional[str] = None
    ) -> AgentTaskRecoveryExecutionPreconditionDecision:
        """Decide whether task_id's exact snapshot_id may proceed to
        recovery execution right now.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionError: If
                task_id/snapshot_id is not a non-empty string, or
                authorization_id is given but is not a string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")
        if authorization_id is not None and not isinstance(authorization_id, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionError(
                "authorization_id must be a string when given"
            )

        snapshot = self._snapshot_service.get(task_id, snapshot_id)
        if snapshot is None:
            return self._blocked(
                task_id, snapshot_id, authorization_id, "no snapshot is recorded for this task_id/snapshot_id"
            )
        if authorization_id is not None and snapshot.authorization_id != authorization_id:
            return self._blocked(
                task_id, snapshot_id, snapshot.authorization_id,
                "authorization_id does not match the snapshot's own bound authorization",
            )

        resolved_authorization_id = snapshot.authorization_id

        try:
            reconciliation = self._approval_reconciliation_service.reconcile(task_id, snapshot_id)
        except Exception as error:
            return self._blocked(
                task_id, snapshot_id, resolved_authorization_id,
                f"required precondition evidence could not be computed: {error}",
            )

        # Commit #5's own revalidation is embedded on the reconciliation --
        # `new_drift` is the CURRENT (possibly rebuilt) snapshot's own drift,
        # None only when no active authorization could be resolved at all.
        # Deciding off `new_drift` (never the ORIGINAL snapshot_id's own
        # drift in isolation) is what correctly lets "authorization revoked,
        # but a valid replacement already exists" resolve to REVIEW rather
        # than BLOCK -- the original snapshot's OWN validation is naturally
        # invalid once its authorization is revoked, but that alone must
        # not be conflated with "genuinely unsafe to execute right now."
        new_drift = reconciliation.revalidation.new_drift
        validation_result = new_drift.validation if new_drift is not None else None
        warnings = tuple(validation_result.warnings) if validation_result is not None else ()

        if new_drift is None or not new_drift.execution_may_continue:
            decision = EXECUTION_DECISION_BLOCK
            blocking_conditions = validation_result.blocking_reasons if validation_result is not None else ()
            reason = (
                "; ".join(blocking_conditions)
                or reconciliation.revalidation.reason
                or "the execution precondition is no longer valid"
            )
        elif new_drift.category == DRIFT_REQUIRES_REVALIDATION:
            decision = EXECUTION_DECISION_REVIEW
            reason = "material drift was detected and requires human review before execution can proceed"
            blocking_conditions = ()
        elif reconciliation.state != RECONCILED_PRESERVED:
            decision = EXECUTION_DECISION_REVIEW
            reason = reconciliation.reason
            blocking_conditions = ()
        else:
            decision = EXECUTION_DECISION_ALLOW
            reason = "the execution precondition is valid, approval is applicable, and no blocking drift was detected"
            blocking_conditions = ()

        return AgentTaskRecoveryExecutionPreconditionDecision(
            task_id=task_id, snapshot_id=snapshot_id, authorization_id=resolved_authorization_id,
            decision=decision, reason=reason, blocking_conditions=blocking_conditions, warnings=warnings,
            validation_result=validation_result, drift_classification=new_drift, approval_reconciliation=reconciliation,
            created_at=self._now(),
        )

    def is_allowed(self, task_id: str, snapshot_id: str, authorization_id: Optional[str] = None) -> bool:
        """The same check as decide(), reduced to a bare bool."""
        return self.decide(task_id, snapshot_id, authorization_id).decision == EXECUTION_DECISION_ALLOW

    def _blocked(
        self, task_id: str, snapshot_id: str, authorization_id: Optional[str], reason: str
    ) -> AgentTaskRecoveryExecutionPreconditionDecision:
        return AgentTaskRecoveryExecutionPreconditionDecision(
            task_id=task_id, snapshot_id=snapshot_id, authorization_id=authorization_id,
            decision=EXECUTION_DECISION_BLOCK, reason=reason, blocking_conditions=(reason,), warnings=(),
            validation_result=None, drift_classification=None, approval_reconciliation=None,
            created_at=self._now(),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionError(
                f"{field_name} is required and must be a non-empty string"
            )
