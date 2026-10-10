import pytest

from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_event_analytics import (
    LLMAgentTaskEventFailureClassifier,
    LLMAgentTaskEventFailureRecoveryPlanner,
)
from backend.agent_task_events import (
    LIFECYCLE_TRANSITIONED,
    InMemoryAgentTaskEventStore,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventReplayService,
    LLMAgentTaskEventService,
)
from backend.agent_task_lifecycle import (
    COMPLETED,
    FAILED,
    PLANNED,
    READY,
    RUNNING,
    LLMAgentTaskLifecycleService,
)
from backend.agent_task_queue_retry_eligibility import RetryEligibilityResult
from backend.agent_task_readiness import AgentTaskReadinessCheck, AgentTaskReadinessResult
from backend.agent_task_recovery_guardrails import (
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryGuardService,
    LLMAgentTaskRecoveryPreflightApprovalService,
    LLMAgentTaskRecoveryPreflightAuthorizationService,
    LLMAgentTaskRecoveryPreflightAuthorizationValidationService,
    LLMAgentTaskRecoveryPreflightFreshnessService,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightService,
    LLMAgentTaskRecoveryPreflightStore,
)
from backend.agent_task_recovery_schedule_dependencies import (
    CHANGE_CHANGED,
    CHANGE_FAILED,
    CHANGE_NEWLY_BLOCKED,
    CHANGE_REMOVED,
    CHANGE_RESOLVED,
    UNDETERMINED,
    InMemoryAgentTaskRecoveryScheduleDependencyObservationStore,
    InvalidAgentTaskRecoveryScheduleDependencyReconciliationError,
    LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyService,
)
from backend.agent_task_recovery_scheduling import (
    InvalidAgentTaskRecoveryScheduleDispatchError,
    LLMAgentTaskRecoveryPreflightScheduleDispatchService,
    LLMAgentTaskRecoveryPreflightSchedulingService,
    LLMAgentTaskRecoveryPreflightScheduleValidationService,
)


class _FakeReadinessService:
    def __init__(self, policy_passed=True, dependencies_passed=True):
        self.set(policy_passed=policy_passed, dependencies_passed=dependencies_passed)

    def set(self, policy_passed=True, dependencies_passed=True):
        checks = [
            AgentTaskReadinessCheck(name="lifecycle_state", passed=True),
            AgentTaskReadinessCheck(
                name="dependencies", passed=dependencies_passed,
                detail=None if dependencies_passed else "dependency X is not yet resolved",
            ),
            AgentTaskReadinessCheck(
                name="policy", passed=policy_passed, detail=None if policy_passed else "policy denies task execution"
            ),
        ]
        blocking = [c.detail for c in checks if not c.passed and c.detail]
        self._result = AgentTaskReadinessResult(
            ready=not blocking, task_id="unused", blocking_reasons=blocking, warnings=[], checks=checks
        )

    def check(self, task_id):
        return self._result


class _FakeRetryEligibilityService:
    def __init__(self, eligible=True, reason="eligible"):
        self._result = RetryEligibilityResult(task_id="unused", eligible=eligible, reason=reason)

    def check(self, task_id):
        return self._result


class _FakeRetryScheduler:
    def get_retry_schedule(self, task_id):
        return None


class _FakeDeadLetterService:
    def get(self, task_id):
        return None


class _FakeReservationService:
    def is_reservation_valid(self, task_id):
        return False


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "recover the task"}
    definition.update(overrides)
    return definition


def _task(lifecycle_service, **overrides):
    return lifecycle_service.create(_definition(**overrides))


def _advance_to(lifecycle_service, task, state):
    for target in (PLANNED, READY, RUNNING):
        if task.current_state == state:
            return task
        task = lifecycle_service.transition(task.task_id, target)
    return lifecycle_service.transition(task.task_id, state) if task.current_state != state else task


def _stack():
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    replay_service = LLMAgentTaskEventReplayService(query_service=query_service)

    readiness = _FakeReadinessService()
    retry_eligibility = _FakeRetryEligibilityService()

    planner = LLMAgentTaskEventFailureRecoveryPlanner(
        classifier=classifier, readiness_service=readiness, retry_eligibility_service=retry_eligibility
    )
    guard = LLMAgentTaskRecoveryGuardService(
        classifier=classifier, replay_service=replay_service,
        readiness_service=readiness, retry_eligibility_service=retry_eligibility,
        retry_scheduler=_FakeRetryScheduler(), dead_letter_service=_FakeDeadLetterService(),
        reservation_service=_FakeReservationService(),
    )
    evaluation_service = LLMAgentTaskRecoveryGuardEvaluationService(guard_service=guard)
    preflight_service = LLMAgentTaskRecoveryPreflightService(planner=planner, evaluation_service=evaluation_service)
    preflight_store = LLMAgentTaskRecoveryPreflightStore()
    freshness_service = LLMAgentTaskRecoveryPreflightFreshnessService(
        preflight_store=preflight_store, classifier=classifier, replay_service=replay_service,
        readiness_service=readiness, retry_eligibility_service=retry_eligibility,
    )
    invalidation_service = LLMAgentTaskRecoveryPreflightInvalidationService(
        preflight_store=preflight_store, freshness_service=freshness_service
    )
    approval_service = LLMAgentTaskRecoveryPreflightApprovalService(
        preflight_store=preflight_store, invalidation_service=invalidation_service
    )
    authorization_service = LLMAgentTaskRecoveryPreflightAuthorizationService(
        preflight_store=preflight_store, approval_service=approval_service,
        invalidation_service=invalidation_service, evaluation_service=evaluation_service,
    )
    authorization_validation_service = LLMAgentTaskRecoveryPreflightAuthorizationValidationService(
        authorization_service=authorization_service, preflight_store=preflight_store,
        invalidation_service=invalidation_service, freshness_service=freshness_service,
        approval_service=approval_service, evaluation_service=evaluation_service,
    )
    scheduling_service = LLMAgentTaskRecoveryPreflightSchedulingService(
        approval_service=approval_service, authorization_service=authorization_service,
        validation_service=authorization_validation_service,
    )

    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    gate_service = LLMAgentTaskRecoveryPreflightScheduleDependencyService(
        scheduling_service=scheduling_service, dependency_resolver=dependency_resolver
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService(
        scheduling_service=scheduling_service, dependency_service=gate_service, dependency_resolver=dependency_resolver
    )
    reconciled_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
        dependency_service=reconciliation_service,
    )
    dispatch_service = LLMAgentTaskRecoveryPreflightScheduleDispatchService(
        validation_service=reconciled_validation_service, scheduling_service=scheduling_service,
    )

    lifecycle_service.create(_definition(task_id="task-1"))

    return {
        "event_service": event_service,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "approval_service": approval_service,
        "scheduling_service": scheduling_service,
        "lifecycle_service": lifecycle_service,
        "dependency_service": dependency_service,
        "dependency_resolver": dependency_resolver,
        "gate_service": gate_service,
        "reconciliation_service": reconciliation_service,
        "reconciled_validation_service": reconciled_validation_service,
        "dispatch_service": dispatch_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


def _scheduled(s, task_id="task-1", execute_at=None):
    preflight = s["preflight_store"].save(s["preflight_service"].run(task_id))
    s["approval_service"].request(task_id, preflight.preflight_id)
    s["approval_service"].approve(task_id, preflight.preflight_id, actor="alice")
    schedule = s["scheduling_service"].schedule(task_id, preflight.preflight_id, execute_at=execute_at)
    return preflight, schedule


# --- baseline / unchanged dependencies --------------------------------------------------


def test_first_reconciliation_establishes_baseline_with_no_changes():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    result = s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)

    assert len(result.observations) == 1
    assert result.observations[0].ready is False
    assert result.changes == ()
    assert result.reliable is True


def test_unchanged_dependencies_produce_no_changes_on_repeat():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    first = s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)
    second = s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)

    assert first.observations[0].ready is True
    assert second.changes == ()
    assert second.observations[0].ready == first.observations[0].ready
    assert second.observations[0].state == first.observations[0].state
    # Append-only: each call still records its own new observation row.
    assert len(s["reconciliation_service"].get_history("task-1", schedule.schedule_id)) == 2


# --- newly blocked -----------------------------------------------------------------------


def test_newly_blocked_dependency_detected():
    s = _stack()
    mid = _task(s["lifecycle_service"])
    leaf = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", mid.task_id)
    s["dependency_service"].add_dependency(mid.task_id, leaf.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)
    _advance_to(s["lifecycle_service"], leaf, FAILED)
    result = s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)

    kinds = {change.dependency_task_id: change.kind for change in result.changes}
    assert kinds[leaf.task_id] == CHANGE_FAILED
    assert kinds[mid.task_id] == CHANGE_NEWLY_BLOCKED
    assert result.observations[0].ready is False


# --- resolved ------------------------------------------------------------------------------


def test_resolved_dependency_detected():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    result = s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)

    kinds = {change.dependency_task_id: change.kind for change in result.changes}
    assert kinds[dep.task_id] == CHANGE_RESOLVED
    assert result.observations[0].ready is True


# --- failed --------------------------------------------------------------------------------


def test_dependency_failure_detected():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)
    _advance_to(s["lifecycle_service"], dep, FAILED)
    result = s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)

    kinds = {change.dependency_task_id: change.kind for change in result.changes}
    assert kinds[dep.task_id] == CHANGE_FAILED
    assert result.observations[0].ready is False
    assert result.observations[0].state == "failed"


# --- removed -------------------------------------------------------------------------------


def test_removed_dependency_detected():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)
    s["dependency_service"].remove_dependency("task-1", dep.task_id)
    result = s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)

    kinds = {change.dependency_task_id: change.kind for change in result.changes}
    assert kinds[dep.task_id] == CHANGE_REMOVED
    assert result.observations[0].ready is True


def test_new_dependency_edge_reported_as_changed():
    s = _stack()
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)
    new_dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", new_dep.task_id)
    result = s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)

    kinds = {change.dependency_task_id: change.kind for change in result.changes}
    assert kinds[new_dep.task_id] == CHANGE_CHANGED


# --- repeated reconciliation is idempotent ------------------------------------------------


def test_repeated_reconciliation_is_idempotent():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    results = [s["reconciliation_service"].reconcile("task-1", schedule.schedule_id) for _ in range(3)]

    assert all(r.observations[0].ready is True for r in results)
    assert results[1].changes == ()
    assert results[2].changes == ()


# --- history preservation -----------------------------------------------------------------


def test_history_is_preserved_and_never_mutated():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)
    first_observation_id = s["reconciliation_service"].get_latest("task-1", schedule.schedule_id).observation_id

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)

    history = s["reconciliation_service"].get_history("task-1", schedule.schedule_id)
    assert len(history) == 2
    assert history[0].observation_id == first_observation_id
    assert history[0].ready is False
    assert history[1].ready is True
    # oldest-first ordering
    assert history[0].observed_at <= history[1].observed_at


# --- dispatch eligibility changes after reconciliation --------------------------------------


def test_dispatch_eligibility_changes_correctly_after_reconciliation():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    blocked_validation = s["reconciled_validation_service"].validate("task-1", schedule.schedule_id)
    assert blocked_validation.valid is False
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDispatchError):
        s["dispatch_service"].dispatch("task-1", schedule.schedule_id)

    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    ready_validation = s["reconciled_validation_service"].validate("task-1", schedule.schedule_id)
    assert ready_validation.valid is True
    dispatch = s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    assert dispatch.status == "dispatched"

    # validate() itself performed the reconciliation as a side effect.
    history = s["reconciliation_service"].get_history("task-1", schedule.schedule_id)
    assert len(history) >= 2


# --- fail closed -----------------------------------------------------------------------------


def test_fail_closed_when_dependency_state_cannot_be_determined():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    baseline = s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)
    assert baseline.reliable is True

    # A resolver built over an unrelated, empty lifecycle_service can
    # never resolve "task-1" -- resolve() raises UnknownAgentTaskError,
    # simulating "dependency state cannot be determined reliably".
    broken_resolver = LLMAgentTaskDependencyResolver(
        LLMAgentTaskLifecycleService(), LLMAgentTaskDependencyService(LLMAgentTaskLifecycleService())
    )
    broken_reconciliation_service = LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService(
        scheduling_service=s["scheduling_service"], dependency_resolver=broken_resolver,
    )

    result = broken_reconciliation_service.reconcile("task-1", schedule.schedule_id)

    assert result.reliable is False
    assert result.unreliable_schedule_ids == (schedule.schedule_id,)
    observation = result.observations[0]
    assert observation.reliable is False
    assert observation.ready is False
    assert observation.state == UNDETERMINED
    assert any("could not be determined reliably" in blocker for blocker in observation.blockers)
    # An undetermined pass can never itself stand for a real transition.
    assert result.changes == ()


def test_undetermined_observation_is_never_diffed_against():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    shared_store = InMemoryAgentTaskRecoveryScheduleDependencyObservationStore()
    reliable_service = LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService(
        scheduling_service=s["scheduling_service"], dependency_service=s["gate_service"],
        dependency_resolver=s["dependency_resolver"], store=shared_store,
    )
    reliable_service.reconcile("task-1", schedule.schedule_id)

    broken_resolver = LLMAgentTaskDependencyResolver(
        LLMAgentTaskLifecycleService(), LLMAgentTaskDependencyService(LLMAgentTaskLifecycleService())
    )
    broken_service = LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService(
        scheduling_service=s["scheduling_service"], dependency_resolver=broken_resolver, store=shared_store,
    )
    broken_service.reconcile("task-1", schedule.schedule_id)

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    result = reliable_service.reconcile("task-1", schedule.schedule_id)

    # Compared against the undetermined pass immediately before it, so no
    # "resolved" change is reported this time -- documented, conservative
    # fail-closed behavior.
    assert result.changes == ()
    assert result.observations[0].ready is True


# --- argument validation --------------------------------------------------------------------


def test_reconcile_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyReconciliationError):
        s["reconciliation_service"].reconcile("", "id")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyReconciliationError):
        s["reconciliation_service"].reconcile("task-1", "")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyReconciliationError):
        s["reconciliation_service"].reconcile_all("")


# --- never mutates schedule/task state -------------------------------------------------------


def test_reconciliation_never_mutates_schedule_or_task_state():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    s["reconciliation_service"].reconcile("task-1", schedule.schedule_id)

    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "scheduled"
    assert s["lifecycle_service"].get(dep.task_id).current_state == "created"


# --- reconcile_all covers every schedule ------------------------------------------------------


def test_reconcile_all_covers_every_schedule_for_task():
    s = _stack()
    _fail_task(s["event_service"])
    _, schedule_1 = _scheduled(s)
    preflight_2 = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight_2.preflight_id)
    s["approval_service"].approve("task-1", preflight_2.preflight_id, actor="bob")
    schedule_2 = s["scheduling_service"].schedule("task-1", preflight_2.preflight_id)

    result = s["reconciliation_service"].reconcile_all("task-1")

    observed_schedule_ids = {observation.schedule_id for observation in result.observations}
    assert observed_schedule_ids == {schedule_1.schedule_id, schedule_2.schedule_id}


# --- check() bridge ---------------------------------------------------------------------------


def test_check_bridge_returns_observation_and_records_history():
    s = _stack()
    _fail_task(s["event_service"])
    _, schedule = _scheduled(s)

    observation = s["reconciliation_service"].check("task-1", schedule.schedule_id)

    assert observation.ready is True
    assert observation.blockers == ()
    assert len(s["reconciliation_service"].get_history("task-1", schedule.schedule_id)) == 1
