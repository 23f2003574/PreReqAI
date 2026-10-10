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
    APPLIED,
    InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError,
    LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyChangeAuditService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyChangePlanner,
    LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService,
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


class _FlakyWaitService:
    """Wraps a real wait_service, raising unexpectedly for one specific
    schedule_id -- used to exercise the failed-application audit path."""

    def __init__(self, real_wait_service, fails_for_schedule_id):
        self._real = real_wait_service
        self._fails_for = fails_for_schedule_id

    def plan_wait(self, task_id, schedule_id, now=None):
        if schedule_id == self._fails_for:
            raise RuntimeError("simulated transient failure")
        return self._real.plan_wait(task_id, schedule_id, now=now)

    def apply_wait(self, task_id, schedule_id, wait_plan, now=None):
        return self._real.apply_wait(task_id, schedule_id, wait_plan, now=now)


_DEFERRED = object()


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
    # Audit events share the SAME underlying event store the guard/
    # preflight pipeline already uses (Rule: "Reuse existing task-event
    # ... persistence where possible").
    audit_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangeAuditService(
        event_service=event_service, query_service=query_service,
    )
    change_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService(
        planner_service=planner_service, scheduling_service=scheduling_service,
        wait_service=wait_service, wake_service=wake_service,
        escalation_service=escalation_service, timeout_service=timeout_service,
        audit_service=audit_service,
    )

    return {
        "event_service": event_service,
        "query_service": query_service,
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
        "change_service": change_service,
        "audit_service": audit_service,
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


def _task_with_schedule(s, task_id, dep, execute_at=_DEFERRED):
    s["lifecycle_service"].create(_definition(task_id=task_id))
    s["dependency_service"].add_dependency(task_id, dep.task_id)
    _fail_task(s["event_service"], task_id)
    if execute_at is _DEFERRED:
        execute_at = datetime.now(timezone.utc) + timedelta(hours=6)
    _, schedule = _scheduled(s, task_id=task_id, execute_at=execute_at)
    return schedule


# --- every action type ------------------------------------------------------------------------


def test_audit_records_no_op():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    schedule = _task_with_schedule(s, "task-1", dep)
    s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)  # baseline

    s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_NO_OP)

    records = s["audit_service"].get("task-1", schedule.schedule_id)
    assert len(records) == 1
    assert records[0].action == ACTION_NO_OP
    assert records[0].status == APPLIED
    assert records[0].success is True


def test_audit_records_revalidate():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)  # baseline, still pending
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    result = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_REVALIDATE)

    records = s["audit_service"].get("task-1", schedule.schedule_id)
    assert len(records) == 1
    assert records[0].action == ACTION_REVALIDATE
    assert records[0].new_schedule_id == result.new_schedule_id
    assert records[0].resulting_status == "scheduled"


def test_audit_records_wait():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep, execute_at=None)

    s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_WAIT)

    records = s["audit_service"].get("task-1", schedule.schedule_id)
    assert len(records) == 1
    assert records[0].action == ACTION_WAIT
    assert records[0].previous_status == "scheduled"
    assert records[0].resulting_status == "scheduled"


def test_audit_records_escalate():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_ESCALATE, now=far_future)

    records = s["audit_service"].get("task-1", schedule.schedule_id)
    assert len(records) == 1
    assert records[0].action == ACTION_ESCALATE
    assert records[0].new_schedule_id == schedule.schedule_id


def test_audit_records_expire():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    _advance_to(s["lifecycle_service"], dep, FAILED)

    s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_EXPIRE)

    records = s["audit_service"].get("task-1", schedule.schedule_id)
    assert len(records) == 1
    assert records[0].action == ACTION_EXPIRE
    assert records[0].resulting_status == "cancelled"


# --- failure ------------------------------------------------------------------------------------


def test_audit_records_failed_application():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep, execute_at=None)

    flaky_wait_service = _FlakyWaitService(s["wait_service"], fails_for_schedule_id=schedule.schedule_id)
    change_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService(
        planner_service=s["planner_service"], scheduling_service=s["scheduling_service"],
        wait_service=flaky_wait_service, wake_service=s["wake_service"],
        escalation_service=s["escalation_service"], timeout_service=s["timeout_service"],
        audit_service=s["audit_service"],
    )

    plan = s["planner_service"].plan("task-1")
    result = change_service.apply("task-1", plan)
    assert result.results[0].status == "failed"

    records = s["audit_service"].get("task-1", schedule.schedule_id)
    assert len(records) == 1
    assert records[0].status == "failed"
    assert records[0].success is False
    assert "simulated transient failure" in records[0].reason


# --- duplicate recording -----------------------------------------------------------------------


def test_duplicate_recording_is_prevented():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    result = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_ESCALATE, now=far_future)

    # An accidental retry recording the IDENTICAL change_result again
    # must never create a second entry.
    first = s["audit_service"].record("task-1", schedule.schedule_id, result)
    second = s["audit_service"].record("task-1", schedule.schedule_id, result)

    assert first.audit_id == second.audit_id
    records = s["audit_service"].get("task-1", schedule.schedule_id)
    assert len(records) == 1


# --- correct IDs ---------------------------------------------------------------------------------


def test_audit_captures_correct_ids():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)
    s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_ESCALATE, now=far_future)

    record = s["audit_service"].get("task-1", schedule.schedule_id)[0]
    assert record.task_id == "task-1"
    assert record.schedule_id == schedule.schedule_id
    assert record.preflight_id == schedule.preflight_id
    assert record.dependency_id is None or isinstance(record.dependency_id, str)
    assert record.dependency_evidence != ()


# --- history preservation ------------------------------------------------------------------------


def test_audit_history_is_append_only_and_preserved():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_ESCALATE, now=far_future)
    first_records = s["audit_service"].get("task-1", schedule.schedule_id)
    assert len(first_records) == 1

    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    s["escalation_resolution_service"].resolve("task-1", schedule.schedule_id, now=far_future)

    later_records = s["audit_service"].get("task-1", schedule.schedule_id)
    assert len(later_records) >= 1
    assert later_records[0] == first_records[0]  # the original entry is never rewritten


def test_list_covers_every_schedule_for_a_task():
    # Two genuinely independent records for the same task, via the
    # established block -> plan_wait -> apply_wait technique.
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule_a = _task_with_schedule(s, "task-1", dep, execute_at=None)
    s["blocking_service"].block("task-1", schedule_a.schedule_id, (dep.task_id,), "waiting on dep")
    wait_plan = s["wait_service"].plan_wait("task-1", schedule_a.schedule_id)
    schedule_b = s["wait_service"].apply_wait("task-1", schedule_a.schedule_id, wait_plan)

    plan = s["planner_service"].plan("task-1")
    s["change_service"].apply("task-1", plan)

    all_records = s["audit_service"].list("task-1")
    schedule_ids = {record.schedule_id for record in all_records}
    assert schedule_a.schedule_id in schedule_ids
    assert schedule_b.schedule_id in schedule_ids
    assert s["audit_service"].get("task-1", schedule_a.schedule_id) != []
    assert s["audit_service"].get("task-1", schedule_b.schedule_id) != []


def test_get_and_list_never_raise_for_no_recorded_audits():
    s = _stack()
    assert s["audit_service"].get("task-1", "never-existed") == []
    assert s["audit_service"].list("task-1") == []


# --- never alters scheduling decisions ------------------------------------------------------------


def test_audit_never_mutates_scheduling_state():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)
    result = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_ESCALATE, now=far_future)

    before = s["scheduling_service"].get("task-1", schedule.schedule_id)
    s["audit_service"].record("task-1", schedule.schedule_id, result)
    after = s["scheduling_service"].get("task-1", schedule.schedule_id)

    assert before == after


# --- argument validation ----------------------------------------------------------------------------


def test_record_rejects_invalid_arguments():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)
    result = s["change_service"].apply_schedule("task-1", schedule.schedule_id, ACTION_ESCALATE, now=far_future)

    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError):
        s["audit_service"].record("", schedule.schedule_id, result)
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError):
        s["audit_service"].record("task-1", "", result)
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError):
        s["audit_service"].record("task-1", schedule.schedule_id, "not-a-result")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError):
        s["audit_service"].record("task-2", schedule.schedule_id, result)  # task_id mismatch


def test_get_and_list_reject_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError):
        s["audit_service"].get("", "id")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError):
        s["audit_service"].get("task-1", "")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError):
        s["audit_service"].list("")
