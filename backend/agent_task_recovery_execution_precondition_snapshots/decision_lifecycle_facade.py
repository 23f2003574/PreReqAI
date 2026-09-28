from dataclasses import dataclass
from datetime import datetime, timezone

from .models import IMPACT_RECONCILIATION_REPLACED


class InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError(ValueError):
    """Raised when evaluate() is given an invalid task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionLifecycleFacadeResult:
    """LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade.evaluate()'s
    consolidated outcome -- every field is copied verbatim from whichever
    existing service actually computed it; this facade computes nothing
    of its own."""

    task_id: str
    authoritative_decision_id: object
    decision_lineage_status: str
    affected_artifacts: tuple
    lifecycle_result_id: str
    remediation_operation_id: object
    reconciliation_state: object
    reconciliation_operation_id: object
    blockers: tuple
    final_verification_status: str
    evaluated_at: datetime


class LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade:
    """Application-facing integration boundary over the existing
    decision, supersession, impact, invalidation, reconciliation, audit
    and verification services already implemented in this package.

    Before this, a caller wanting to know "is this task's recovery
    execution decision still good, and if not, what already happened
    about it" had to call the supersession validation service, the
    impact-invalidation lifecycle service (or, on a repeat call, the
    reconciliation service instead -- picking the right one is itself a
    judgment call), and the lifecycle verification service separately,
    in the right order, and merge their three separate result shapes by
    hand. This composes exactly that sequence -- authoritative decision
    (via supersession resolution, inside the lifecycle service) ->
    supersession validation -> decision-change impact analysis ->
    staleness detection -> the existing remediation/reconciliation
    lifecycle -> final verification -- behind one evaluate(task_id) call,
    without changing what any of them decide.

    Never executes recovery itself: it only ever calls run()/reconcile()
    on the existing lifecycle/reconciliation services, which themselves
    stop at planning+applying invalidation actions, never at actually
    retrying/resuming the task's own recovery. Never duplicates a
    business rule any composed service already owns -- resolution,
    impact classification, staleness, remediation planning/execution,
    and verification all stay exactly where they already are; this class
    only calls them in order and reads their own results.

    Idempotent the same way the composed services already are: a first
    evaluate(task_id) for a task with no persisted lifecycle result runs
    the remediation lifecycle and persists it; every subsequent
    evaluate(task_id) reconciles that persisted result against current
    state (via the existing reconciliation service) instead of blindly
    re-running remediation -- NO_OP when nothing has changed, exactly
    the reconciliation service's own contract.
    """

    def __init__(
        self,
        supersession_validation_service,
        lifecycle_service,
        lifecycle_result_service,
        lifecycle_verification_service,
        reconciliation_service,
    ):
        """All five are the existing services from this package -- see
        LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycle
        ReconciliationService's own constructor (decision_impact_
        invalidation_lifecycle_reconciliation.py) for the reference
        wiring every argument here must share stores with."""
        self._supersession_validation = supersession_validation_service
        self._lifecycle = lifecycle_service
        self._results = lifecycle_result_service
        self._verification = lifecycle_verification_service
        self._reconciliation = reconciliation_service

    def evaluate(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionLifecycleFacadeResult:
        """Evaluate task_id's current recovery execution decision
        lifecycle end to end.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError:
                If task_id is not a non-empty string
        Also propagates, unchanged, whatever error any composed service
        itself raises (e.g. a store failure) -- this never catches or
        reinterprets a composed service's own diagnostics.
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError(
                "task_id is required and must be a non-empty string"
            )

        supersession = self._supersession_validation.validate(task_id)

        existing = self._results.latest(task_id)
        reconciliation = None
        if existing is None:
            lifecycle_result = self._lifecycle.run(task_id)
            record = self._results.record(task_id, lifecycle_result)
        else:
            reconciliation = self._reconciliation.reconcile(task_id, existing.result_id)
            record = (
                self._results.get(task_id, reconciliation.replacement_result_id)
                if reconciliation.state == IMPACT_RECONCILIATION_REPLACED
                else existing
            )

        verification = self._verification.verify(task_id, record.result_id)

        blockers = tuple(record.blocking_artifacts) + tuple(verification.remaining_blockers)

        return AgentTaskRecoveryExecutionDecisionLifecycleFacadeResult(
            task_id=task_id,
            authoritative_decision_id=record.authoritative_decision_id,
            decision_lineage_status=supersession.status,
            affected_artifacts=tuple(record.affected_artifacts),
            lifecycle_result_id=record.result_id,
            remediation_operation_id=record.operation_id,
            reconciliation_state=reconciliation.state if reconciliation is not None else None,
            reconciliation_operation_id=(
                reconciliation.replacement_operation_id if reconciliation is not None else None
            ),
            blockers=blockers,
            final_verification_status=verification.status,
            evaluated_at=datetime.now(timezone.utc),
        )
