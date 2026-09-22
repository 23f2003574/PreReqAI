from datetime import datetime, timezone

from .decision import LLMAgentTaskRecoveryExecutionPreconditionDecisionService
from .decision_integrity import LLMAgentTaskRecoveryExecutionDecisionIntegrityService
from .decision_staleness import LLMAgentTaskRecoveryExecutionDecisionStalenessService
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import (
    FRESHNESS_FRESH,
    INTEGRITY_VALID,
    REVALIDATION_FAILED,
    REVALIDATION_REPLACED,
    REVALIDATION_REUSED,
    AgentTaskRecoveryExecutionDecisionFreshnessRevalidationResult,
)
from .revalidation import LLMAgentTaskRecoveryExecutionPreconditionRevalidationService


class InvalidAgentTaskRecoveryExecutionDecisionFreshnessRevalidationError(ValueError):
    """Raised when revalidate() is given invalid arguments, or
    decision_id names no decision recorded for task_id."""


class LLMAgentTaskRecoveryExecutionDecisionFreshnessRevalidationService:
    """Produces a fresh decision through the EXISTING precondition
    pipeline when a persisted decision is stale/indeterminate -- never a
    second decision engine (Rule: "Do not create another decision
    engine"): every write is delegated -- the earlier series' own
    LLMAgentTaskRecoveryExecutionPreconditionRevalidationService.revalidate()
    (rebuilds the snapshot, resolving a currently-ACTIVE authorization,
    never fabricating one) produces the current snapshot, the earlier
    series' own LLMAgentTaskRecoveryExecutionPreconditionDecisionService.
    decide() (the canonical decision boundary, itself running validation/
    drift/approval-reconciliation unmodified) produces the fresh decision,
    and Commit #7-of-the-earlier-series' own decision store persists it.
    This class only decides WHETHER a rebuild is warranted and links old
    -> new for traceability.

    Never bypasses authorization/approval/precondition validation, and
    never executes recovery (Rule): revalidate() never calls
    execute_plan() or any authorization/approval WRITE method itself --
    decide() is the sole write path exercised, and it is never modified
    or shortcut.

    Never mutates the old decision (Rule): the decision store is
    append-only by construction; old_decision_id's own record is only
    ever read here.

    `decision_service` must NOT be pre-wired with its own persistence
    store (Rule: reuse the SAME store this class itself persists through,
    exactly once) -- passing one wired with a store here would double-
    write the same decision into history (once inside decide(), once
    here), corrupting Commit #10's own chronological aggregates.

    Fails closed if freshness cannot be established safely (Rule):
    Commit #1's own integrity check runs first -- a decision that fails
    it is reported REVALIDATION_FAILED immediately, never guessed fresh.

    Idempotent when the current decision is already equivalent and fresh
    (Rule): after resolving the current target snapshot through the
    earlier series' own revalidate() (itself idempotent -- it reuses an
    existing valid snapshot rather than capturing a new one when nothing
    changed), this class checks whether the task's own latest persisted
    decision is ALREADY bound to that exact snapshot_id -- if so, that
    one is reused outright rather than calling decide() again to mint a
    functionally-identical decision under a new decision_id.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        snapshot_service=None,
        authorization_service=None,
        integrity_service: LLMAgentTaskRecoveryExecutionDecisionIntegrityService = None,
        staleness_service: LLMAgentTaskRecoveryExecutionDecisionStalenessService = None,
        precondition_revalidation_service: LLMAgentTaskRecoveryExecutionPreconditionRevalidationService = None,
        decision_service: LLMAgentTaskRecoveryExecutionPreconditionDecisionService = None,
    ):
        """
        Args:
            decision_store: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionStore;
                pass the real instance holding the decisions decide()
                actually persisted -- this class is the sole place that
                calls save() on it.
            snapshot_service/authorization_service: Forwarded into the
                default integrity_service/staleness_service below when
                those are not given explicitly -- pass the real, already-
                wired instances so those defaults are never disconnected
                from real data (a sharp edge this series has already hit
                twice: a default sub-collaborator must never silently
                build its OWN fresh, disconnected stack).
            integrity_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionDecisionIntegrityService
                built from decision_store/snapshot_service/
                authorization_service above.
            staleness_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionDecisionStalenessService
                built from decision_store/snapshot_service/
                authorization_service above.
            precondition_revalidation_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionRevalidationService
                (the earlier series' own #4); pass the real instance
                wired to the same snapshot/authorization stack.
            decision_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionService
                (the earlier series' own #6) built WITHOUT its own store
                (see class docstring); pass a real instance wired to the
                same guard/approval-reconciliation stack, still without a
                store of its own.
        """
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._integrity_service = (
            integrity_service
            if integrity_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionIntegrityService(
                decision_store=self._decision_store, snapshot_service=snapshot_service,
                authorization_service=authorization_service,
            )
        )
        self._staleness_service = (
            staleness_service
            if staleness_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionStalenessService(
                decision_store=self._decision_store, snapshot_service=snapshot_service,
                authorization_service=authorization_service,
            )
        )
        self._precondition_revalidation_service = (
            precondition_revalidation_service
            if precondition_revalidation_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionRevalidationService()
        )
        self._decision_service = (
            decision_service if decision_service is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionService()
        )

    def revalidate(
        self, task_id: str, decision_id: str
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessRevalidationResult:
        """Revalidate task_id's exact decision_id, producing and
        persisting a fresh decision through the existing pipeline if
        needed.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionFreshnessRevalidationError:
                If task_id/decision_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(decision_id, "decision_id")

        integrity = self._integrity_service.check(task_id, decision_id)
        old_decision = self._decision_store.get(decision_id)
        staleness = self._staleness_service.check(task_id, decision_id)

        if integrity.status != INTEGRITY_VALID or old_decision is None:
            return self._result(
                task_id, decision_id, REVALIDATION_FAILED, staleness, old_decision, None,
                f"decision integrity check failed: {'; '.join(integrity.issues) or 'decision not found'}",
            )

        if staleness.status == FRESHNESS_FRESH:
            return self._result(task_id, decision_id, REVALIDATION_REUSED, staleness, old_decision, old_decision, None)

        precondition_revalidation = self._precondition_revalidation_service.revalidate(
            task_id, old_decision.snapshot_id
        )
        if precondition_revalidation.new_snapshot_id is None:
            return self._result(
                task_id, decision_id, REVALIDATION_FAILED, staleness, old_decision, None,
                precondition_revalidation.reason or "no current precondition snapshot could be established",
            )

        # Idempotent: a decision already persisted for this EXACT target
        # snapshot means the pipeline already produced today's answer for
        # it -- reuse it rather than minting a functionally-identical
        # decision under a new decision_id every call.
        latest = self._decision_store.latest(task_id)
        if latest is not None and latest.snapshot_id == precondition_revalidation.new_snapshot_id:
            return self._result(task_id, decision_id, REVALIDATION_REUSED, staleness, old_decision, latest, None)

        new_decision = self._decision_service.decide(task_id, precondition_revalidation.new_snapshot_id)
        persisted_decision = self._decision_store.save(new_decision)

        return self._result(
            task_id, decision_id, REVALIDATION_REPLACED, staleness, old_decision, persisted_decision, None
        )

    def _result(
        self, task_id, old_decision_id, action, staleness, old_decision, new_decision, reason
    ) -> AgentTaskRecoveryExecutionDecisionFreshnessRevalidationResult:
        return AgentTaskRecoveryExecutionDecisionFreshnessRevalidationResult(
            task_id=task_id, old_decision_id=old_decision_id,
            new_decision_id=new_decision.decision_id if new_decision is not None else None,
            action=action, staleness=staleness, old_decision=old_decision, new_decision=new_decision,
            reason=reason, revalidated_at=self._now(),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionFreshnessRevalidationError(
                f"{field_name} is required and must be a non-empty string"
            )
