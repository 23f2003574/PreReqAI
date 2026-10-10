from datetime import datetime, timedelta, timezone

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
from backend.agent_task_queue_retry_eligibility import RetryEligibilityResult
from backend.agent_task_recovery_schedule_dependencies import (
    ACTION_ESCALATE,
    ACTION_EXPIRE,
    ACTION_NO_OP,
    ACTION_REVALIDATE,
    ACTION_WAIT,
    InvalidAgentTaskRecoveryScheduleDependencyChangePlanError,
    LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner,
    LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationResolutionService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyImpactService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyWaitService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService,
)
from backend.agent_task_recovery_scheduling import (
    LLMAgentTaskRecoveryPreflightScheduleExpirationService,
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
    plain_validation_service = LLMAgentTaskRecoveryPreflightScheduleValidationService(
        scheduling_service=scheduling_service, authorization_validation_service=authorization_validation_service,
    )
    expiration_service = LLMAgentTaskRecoveryPreflightScheduleExpirationService(scheduling_service=scheduling_service)

    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    gate_service = LLMAgentTaskRecoveryPreflightScheduleDependencyService(
        scheduling_service=scheduling_service, dependency_resolver=dependency_resolver
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService(
        scheduling_service=scheduling_service, dependency_service=gate_service, dependency_resolver=dependency_resolver
    )
    blocking_service = LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService(
        dependency_service=gate_service, scheduling_service=scheduling_service,
        validation_service=plain_validation_service, expiration_service=expiration_service,
    )
    timeout_service = LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService(
        dependency_service=gate_service, scheduling_service=scheduling_service,
        blocking_service=blocking_service, expiration_service=expiration_service,
        max_wait_duration=timedelta(hours=1),
    )
    escalation_service = LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService(
        timeout_service=timeout_service, scheduling_service=scheduling_service,
    )
    wake_service = LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService(
        reconciliation_service=reconciliation_service, scheduling_service=scheduling_service,
        validation_service=plain_validation_service, expiration_service=expiration_service,
        blocking_service=blocking_service,
    )
    escalation_resolution_service = LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationResolutionService(
        escalation_service=escalation_service, wake_service=wake_service,
        reconciliation_service=reconciliation_service, scheduling_service=scheduling_service,
    )
    wait_service = LLMAgentTaskRecoveryPreflightScheduleDependencyWaitService(
        dependency_service=gate_service, scheduling_service=scheduling_service,
        validation_service=plain_validation_service, expiration_service=expiration_service,
    )
    impact_service = LLMAgentTaskRecoveryPreflightScheduleDependencyImpactService(
        reconciliation_service=reconciliation_service, scheduling_service=scheduling_service,
        timeout_service=timeout_service,
    )
    planner_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner(
        impact_service=impact_service, scheduling_service=scheduling_service,
        escalation_service=escalation_service, escalation_resolution_service=escalation_resolution_service,
    )

    return {
        "event_service": event_service,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "approval_service": approval_service,
        "authorization_service": authorization_service,
        "scheduling_service": scheduling_service,
        "lifecycle_service": lifecycle_service,
        "dependency_service": dependency_service,
        "gate_service": gate_service,
        "reconciliation_service": reconciliation_service,
        "blocking_service": blocking_service,
        "timeout_service": timeout_service,
        "escalation_service": escalation_service,
        "escalation_resolution_service": escalation_resolution_service,
        "wake_service": wake_service,
        "wait_service": wait_service,
        "impact_service": impact_service,
        "planner_service": planner_service,
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


def _task_with_schedule(s, task_id, dep):
    s["lifecycle_service"].create(_definition(task_id=task_id))
    s["dependency_service"].add_dependency(task_id, dep.task_id)
    _fail_task(s["event_service"], task_id)
    _, schedule = _scheduled(s, task_id=task_id, execute_at=datetime.now(timezone.utc) + timedelta(hours=6))
    return schedule


# --- action: no_op ---------------------------------------------------------------------------


def test_action_no_op_when_ready_and_unchanged():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    schedule = _task_with_schedule(s, "task-1", dep)

    s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)  # baseline reconciliation
    plan = s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)

    item = plan.items[0]
    assert item.action == ACTION_NO_OP
    assert item.affected_service is None
    assert item.conflict is None


# --- action: revalidate -----------------------------------------------------------------------


def test_action_revalidate_when_dependency_resolves():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)

    s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)  # baseline, still pending
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    plan = s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)

    item = plan.items[0]
    assert item.action == ACTION_REVALIDATE
    assert "WakeService" in item.affected_service


# --- action: wait -----------------------------------------------------------------------------


def test_action_wait_when_blocked_and_not_timed_out():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)

    plan = s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)

    item = plan.items[0]
    assert item.action == ACTION_WAIT
    assert "WaitService" in item.affected_service


# --- action: escalate --------------------------------------------------------------------------


def test_action_escalate_when_wait_exceeds_timeout_threshold():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    plan = s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id, now=far_future)

    item = plan.items[0]
    assert item.action == ACTION_ESCALATE
    assert "EscalationService" in item.affected_service


# --- action: expire -----------------------------------------------------------------------------


def test_action_expire_when_schedule_no_longer_viable():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="no longer needed")

    plan = s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)

    item = plan.items[0]
    assert item.action == ACTION_EXPIRE
    assert "TimeoutService" in item.affected_service


# --- incomplete dependency evidence ----------------------------------------------------------------


def test_no_action_when_evidence_is_insufficient():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)

    broken_resolver = LLMAgentTaskDependencyResolver(
        LLMAgentTaskLifecycleService(), LLMAgentTaskDependencyService(LLMAgentTaskLifecycleService())
    )
    broken_reconciliation_service = LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService(
        scheduling_service=s["scheduling_service"], dependency_resolver=broken_resolver,
    )
    impact_service = LLMAgentTaskRecoveryPreflightScheduleDependencyImpactService(
        reconciliation_service=broken_reconciliation_service, scheduling_service=s["scheduling_service"],
    )
    planner_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner(
        impact_service=impact_service, scheduling_service=s["scheduling_service"],
    )

    plan = planner_service.plan("task-1", schedule_id=schedule.schedule_id)

    item = plan.items[0]
    assert item.action is None
    assert item.evidence_sufficient is False
    assert item.conflict is None


# --- conflicting actions -----------------------------------------------------------------------------


def test_conflicting_actions_detected_when_escalated_but_now_ready():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)
    s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)  # baseline, still pending
    s["escalation_service"].escalate("task-1", schedule.schedule_id, now=far_future)

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    plan = s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id, now=far_future)

    item = plan.items[0]
    assert item.action is None
    assert item.conflict is not None
    assert set(item.conflict.candidate_actions) == {ACTION_ESCALATE, ACTION_REVALIDATE}


def test_no_conflict_once_escalation_is_resolved():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)
    s["escalation_service"].escalate("task-1", schedule.schedule_id, now=far_future)

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    s["escalation_resolution_service"].resolve("task-1", schedule.schedule_id, now=far_future)

    plan = s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id, now=far_future)

    item = plan.items[0]
    assert item.conflict is None
    # The schedule was superseded by wake() during resolution -- this
    # plan is about the ORIGINAL (now cancelled) schedule_id.
    assert item.action == ACTION_EXPIRE


# --- multiple affected schedules --------------------------------------------------------------------


def test_multiple_affected_schedules_across_tasks():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule_1 = _task_with_schedule(s, "task-1", dep)
    schedule_2 = _task_with_schedule(s, "task-2", dep)
    _advance_to(s["lifecycle_service"], dep, FAILED)

    plan_1 = s["planner_service"].plan("task-1")
    plan_2 = s["planner_service"].plan("task-2")

    assert len(plan_1.items) == 1
    assert plan_1.items[0].schedule_id == schedule_1.schedule_id
    assert plan_1.items[0].action == ACTION_EXPIRE
    assert len(plan_2.items) == 1
    assert plan_2.items[0].schedule_id == schedule_2.schedule_id


def test_ordering_across_multiple_schedules_in_one_task():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    s["lifecycle_service"].create(_definition(task_id="task-1"))
    s["dependency_service"].add_dependency("task-1", dep.task_id)
    _fail_task(s["event_service"])
    # execute_at=None (immediately due) -- plan_wait()'s own validate()
    # call always reads the real wall clock, so a schedule deferred into
    # the future (this package's usual "blocked" convention elsewhere)
    # would fail its own window check before ever reaching the
    # dependency check this test actually cares about.
    _, schedule_a = _scheduled(s)
    s["blocking_service"].block("task-1", schedule_a.schedule_id, (dep.task_id,), "waiting on dep")
    wait_plan = s["wait_service"].plan_wait("task-1", schedule_a.schedule_id)
    schedule_b = s["wait_service"].apply_wait("task-1", schedule_a.schedule_id, wait_plan)

    plan = s["planner_service"].plan("task-1")

    assert len(plan.items) == 2
    # schedule_a is now cancelled (superseded) -> expire, highest priority (0);
    # schedule_b is the new, still-blocked record -> wait, lower priority.
    assert plan.items[0].schedule_id == schedule_a.schedule_id
    assert plan.items[0].action == ACTION_EXPIRE
    assert plan.items[0].sequence == 0
    assert plan.items[1].schedule_id == schedule_b.schedule_id
    assert plan.items[1].action == ACTION_WAIT
    assert plan.items[1].sequence == 1


# --- deterministic plans -----------------------------------------------------------------------------


def test_deterministic_repeated_planning():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)

    first = s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)
    second = s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)

    assert first.items[0].action == second.items[0].action
    assert first.items[0].reason == second.items[0].reason
    assert first.items[0].sequence == second.items[0].sequence


# --- proof planning causes no state changes -----------------------------------------------------------


def test_planning_never_mutates_any_state():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)

    s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)

    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "scheduled"
    assert s["lifecycle_service"].get(dep.task_id).current_state == "created"
    assert s["escalation_service"].get_history("task-1", schedule.schedule_id) == []
    assert s["blocking_service"].get_history("task-1", schedule.schedule_id) == []


# --- argument validation -----------------------------------------------------------------------------


def test_plan_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangePlanError):
        s["planner_service"].plan("")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangePlanError):
        s["planner_service"].plan("task-1", schedule_id="")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangePlanError):
        s["planner_service"].plan("task-1", dependency_id="")


def test_plan_rejects_unknown_schedule():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangePlanError):
        s["planner_service"].plan("task-1", schedule_id="never-existed")
