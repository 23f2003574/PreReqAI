from uuid import uuid4

from backend.agent_task_events import LLMAgentTaskEventService

from .models import (
    AgentTaskRecoveryExecutionDecisionLifecycleResult,
    IMPACT_LIFECYCLE_CLEAN,
    IMPACT_LIFECYCLE_REMEDIATED,
    IMPACT_LIFECYCLE_UP_TO_DATE,
    IMPACT_RECONCILIATION_REPLACED,
    LIFECYCLE_VERIFICATION_VALID,
)

# This facade's own event_type vocabulary (documented, not enforced --
# the same "known key vocabulary, not a closed enum" discipline
# backend.agent_task_events.models.KNOWN_EVENT_TYPES already uses). Not
# added to that module's own KNOWN_EVENT_TYPES: these describe this
# lifecycle's own stages, not a concept backend.agent_task_events'
# existing families (lifecycle transitions, dependencies, readiness,
# retries, context) already own.
LIFECYCLE_STARTED = "lifecycle_started"
DECISION_RESOLVED = "decision_resolved"
IMPACT_ANALYZED = "impact_analyzed"
STALE_ARTIFACTS_DETECTED = "stale_artifacts_detected"
REMEDIATION_STARTED = "remediation_started"
RECONCILIATION_STARTED = "reconciliation_started"
LIFECYCLE_VERIFIED = "lifecycle_verified"
LIFECYCLE_BLOCKED = "lifecycle_blocked"
LIFECYCLE_FAILED = "lifecycle_failed"
LIFECYCLE_COMPLETED = "lifecycle_completed"

_SUCCESS_STATUSES = (IMPACT_LIFECYCLE_REMEDIATED, IMPACT_LIFECYCLE_CLEAN, IMPACT_LIFECYCLE_UP_TO_DATE)


class InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError(ValueError):
    """Raised when evaluate() is given an invalid task_id."""


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
    returning the stable AgentTaskRecoveryExecutionDecisionLifecycleResult
    contract instead of the underlying services' own result shapes,
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

    Observability: every evaluate() call emits a structured event trail
    through the repository's existing append-only event stream
    (backend.agent_task_events.LLMAgentTaskEventService -- "Do not
    invent a second event bus or generic audit framework"), never a new
    logging/metrics/tracing framework of its own. All events from one
    evaluate() call share one correlation_id so they can be pulled back
    as a single trail; the terminal event's operation_id and payload
    reference ids/labels only (no raw decision/snapshot content -- the
    event service's own LLMSecretRedactionService screens payloads
    regardless). This never changes what evaluate() returns: emit()
    failures are not caught here deliberately, the same "a caller must
    only ever call emit() for a change that actually occurred" contract
    LLMAgentTaskEventService itself documents -- an event is only ever
    emitted after the change it describes has already happened.
    """

    def __init__(
        self,
        supersession_validation_service,
        lifecycle_service,
        lifecycle_result_service,
        lifecycle_verification_service,
        reconciliation_service,
        event_service: LLMAgentTaskEventService = None,
    ):
        """The first five are the existing services from this package --
        see LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycle
        ReconciliationService's own constructor (decision_impact_
        invalidation_lifecycle_reconciliation.py) for the reference
        wiring every argument here must share stores with. event_service
        is the existing backend.agent_task_events.LLMAgentTaskEventService;
        when not given, a dedicated one is constructed (the same default
        backend.agent_task_recovery_preflight_dependency_snapshots.
        impact_cache_metrics already uses for its own event stream)."""
        self._supersession_validation = supersession_validation_service
        self._lifecycle = lifecycle_service
        self._results = lifecycle_result_service
        self._verification = lifecycle_verification_service
        self._reconciliation = reconciliation_service
        self._events = event_service if event_service is not None else LLMAgentTaskEventService()

    def evaluate(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionLifecycleResult:
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

        correlation_id = str(uuid4())
        self._emit(task_id, LIFECYCLE_STARTED, correlation_id)

        supersession = self._supersession_validation.validate(task_id)

        existing = self._results.latest(task_id)
        reconciliation = None
        if existing is None:
            self._emit(task_id, REMEDIATION_STARTED, correlation_id)
            lifecycle_result = self._lifecycle.run(task_id)
            record = self._results.record(task_id, lifecycle_result)
        else:
            self._emit(
                task_id, RECONCILIATION_STARTED, correlation_id,
                payload={"previous_lifecycle_result_id": existing.result_id},
            )
            reconciliation = self._reconciliation.reconcile(task_id, existing.result_id)
            record = (
                self._results.get(task_id, reconciliation.replacement_result_id)
                if reconciliation.state == IMPACT_RECONCILIATION_REPLACED
                else existing
            )

        if record.authoritative_decision_id is not None:
            self._emit(
                task_id, DECISION_RESOLVED, correlation_id,
                payload={"authoritative_decision_id": record.authoritative_decision_id},
            )
            self._emit(
                task_id, IMPACT_ANALYZED, correlation_id,
                payload={"affected_artifact_count": len(record.affected_artifacts)},
            )
        if record.remaining_stale:
            self._emit(
                task_id, STALE_ARTIFACTS_DETECTED, correlation_id,
                payload={"stale_artifact_count": len(record.remaining_stale)},
            )

        verification = self._verification.verify(task_id, record.result_id)
        self._emit(
            task_id, LIFECYCLE_VERIFIED, correlation_id, operation_id=record.operation_id,
            payload={"lifecycle_result_id": record.result_id, "verification_status": verification.status},
        )

        blocking_conditions = tuple(record.blocking_artifacts) + tuple(verification.remaining_blockers)
        diagnostics = (
            tuple(record.errors)
            + tuple(verification.mismatches)
            + tuple(verification.missing_evidence)
            + (tuple(reconciliation.issues) if reconciliation is not None else ())
        )

        if blocking_conditions:
            terminal_event = LIFECYCLE_BLOCKED
        elif record.status in _SUCCESS_STATUSES and verification.status == LIFECYCLE_VERIFICATION_VALID:
            terminal_event = LIFECYCLE_COMPLETED
        else:
            terminal_event = LIFECYCLE_FAILED
        self._emit(
            task_id, terminal_event, correlation_id, operation_id=record.operation_id,
            payload={
                "lifecycle_result_id": record.result_id,
                "overall_status": record.status,
                "verification_status": verification.status,
                "blocking_condition_count": len(blocking_conditions),
            },
        )

        return AgentTaskRecoveryExecutionDecisionLifecycleResult(
            task_id=task_id,
            authoritative_decision_id=record.authoritative_decision_id,
            decision_lineage_status=supersession.status,
            affected_artifacts=tuple(record.affected_artifacts),
            remediation_operation_id=record.operation_id,
            reconciliation_operation_id=(
                reconciliation.replacement_operation_id if reconciliation is not None else None
            ),
            blocking_conditions=blocking_conditions,
            verification_status=verification.status,
            overall_status=record.status,
            diagnostics=diagnostics,
        )

    def _emit(self, task_id, event_type, correlation_id, operation_id=None, payload=None):
        self._events.emit(
            task_id, event_type, payload=payload, correlation_id=correlation_id, operation_id=operation_id,
        )
