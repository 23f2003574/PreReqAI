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
    ACTION_NO_OP,
    ACTION_REVALIDATE,
    ACTION_WAIT,
    APPLIED,
    InvalidAgentTaskRecoveryScheduleDependencyChangeOrchestrationError,
    LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyChangeAuditService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyChangeOrchestrationService,
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
    LLMAgentTaskRecoveryPreflightScheduleDispatchService,
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
    schedule_id -- used to exercise the partial-failure path."""

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
    dispatch_service = LLMAgentTaskRecoveryPreflightScheduleDispatchService(
        validation_service=plain_validation_service, scheduling_service=scheduling_service,
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
    # Deliberately built WITHOUT its own audit_service, so the tests can
    # verify the ORCHESTRATOR itself is what records audits, never a
    # side effect it merely happens to inherit.
    change_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService(
        planner_service=planner_service, scheduling_service=scheduling_service,
        wait_service=wait_service, wake_service=wake_service,
        escalation_service=escalation_service, timeout_service=timeout_service,
    )
    audit_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangeAuditService(
        event_service=event_service, query_service=query_service,
    )
    orchestration_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangeOrchestrationService(
        planner_service=planner_service, change_service=change_service, audit_service=audit_service,
        scheduling_service=scheduling_service,
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
        "orchestration_service": orchestration_service,
        "dispatch_service": dispatch_service,
        "validation_service": plain_validation_service,
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


# --- complete flow ------------------------------------------------------------------------------


def test_complete_flow_wait_scenario():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep, execute_at=None)

    result = s["orchestration_service"].process("task-1")

    assert result.task_id == "task-1"
    assert result.affected_schedule_ids == (schedule.schedule_id,)
    assert len(result.planned_actions) == 1
    assert result.planned_actions[0].action == ACTION_WAIT
    assert len(result.applied_actions) == 1
    assert result.applied_actions[0].action == ACTION_WAIT
    assert result.applied_actions[0].status == APPLIED
    assert result.failures == ()
    assert len(result.audit_records) == 1
    assert result.audit_records[0].action == ACTION_WAIT

    # A real state transition actually happened.
    new_record = s["scheduling_service"].get("task-1", result.applied_actions[0].new_schedule_id)
    assert new_record.execute_at is not None


# --- no-impact dependency changes ------------------------------------------------------------------


def test_no_impact_dependency_change():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    schedule = _task_with_schedule(s, "task-1", dep)
    s["orchestration_service"].process("task-1")  # baseline reconciliation

    result = s["orchestration_service"].process("task-1")

    assert len(result.applied_actions) == 1
    assert result.applied_actions[0].action == ACTION_NO_OP
    assert result.failures == ()


# --- stale/conflicting plans (fail closed) ----------------------------------------------------------


def test_conflicting_plan_is_reported_as_a_failure_never_forced():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)
    s["planner_service"].plan("task-1", schedule_id=schedule.schedule_id)  # baseline, still pending
    s["escalation_service"].escalate("task-1", schedule.schedule_id, now=far_future)
    _advance_to(s["lifecycle_service"], dep, COMPLETED)

    result = s["orchestration_service"].process("task-1", now=far_future)

    assert len(result.planned_actions) == 1
    assert result.planned_actions[0].action is None
    assert result.planned_actions[0].conflict is not None
    assert len(result.failures) == 1
    assert result.failures[0].status != APPLIED
    # apply()'s own "action is None" branch uses Commit #10's own
    # conflict.reason verbatim (no "plan is conflicting:" prefix -- that
    # prefix only appears when apply_schedule() itself detects a
    # conflict internally, a different code path than this one).
    assert "already escalated" in result.failures[0].reason
    assert result.applied_actions == ()
    # Never forced into revalidate despite dependencies being ready.
    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "scheduled"


# --- partial failures --------------------------------------------------------------------------------


def test_partial_failures_reported_explicitly():
    # Two genuinely independent records for the same task, via the
    # established block -> plan_wait -> apply_wait technique; the
    # underlying wait_service fails for only the second one.
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule_a = _task_with_schedule(s, "task-1", dep, execute_at=None)
    s["blocking_service"].block("task-1", schedule_a.schedule_id, (dep.task_id,), "waiting on dep")
    wait_plan = s["wait_service"].plan_wait("task-1", schedule_a.schedule_id)
    schedule_b = s["wait_service"].apply_wait("task-1", schedule_a.schedule_id, wait_plan)

    flaky_wait_service = _FlakyWaitService(s["wait_service"], fails_for_schedule_id=schedule_b.schedule_id)
    change_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService(
        planner_service=s["planner_service"], scheduling_service=s["scheduling_service"],
        wait_service=flaky_wait_service, wake_service=s["wake_service"],
        escalation_service=s["escalation_service"], timeout_service=s["timeout_service"],
    )
    orchestration_service = LLMAgentTaskRecoveryPreflightScheduleDependencyChangeOrchestrationService(
        planner_service=s["planner_service"], change_service=change_service, audit_service=s["audit_service"],
        scheduling_service=s["scheduling_service"],
    )

    # schedule_b is already deferred (apply_wait() above just set its own
    # next_check_at ~15min out) -- Commit #11's own idempotency check
    # would otherwise treat it as "already waiting, nothing to do" and
    # never even call the flaky wait_service at all. Process comfortably
    # past that window so a FRESH wait is genuinely attempted.
    later = datetime.now(timezone.utc) + timedelta(minutes=20)
    result = orchestration_service.process("task-1", now=later)

    assert len(result.planned_actions) == 2
    assert len(result.applied_actions) == 1  # schedule_a's own expire
    assert len(result.failures) == 1  # schedule_b's own failed wait
    assert result.failures[0].schedule_id == schedule_b.schedule_id
    assert "simulated transient failure" in result.failures[0].reason
    assert len(result.audit_records) == 2


# --- repeated execution is idempotent -----------------------------------------------------------------


def test_repeated_processing_does_not_duplicate_audits():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    schedule = _task_with_schedule(s, "task-1", dep)

    first = s["orchestration_service"].process("task-1")
    second = s["orchestration_service"].process("task-1")

    assert first.applied_actions[0].action == second.applied_actions[0].action == ACTION_NO_OP
    # Identical no-op outcome both times -> content-based dedup means
    # the SAME audit row, never a duplicate.
    assert first.audit_records[0].audit_id == second.audit_records[0].audit_id
    assert len(s["audit_service"].get("task-1", schedule.schedule_id)) == 1


# --- audit linkage ------------------------------------------------------------------------------------


def test_audit_records_link_to_the_actions_that_produced_them():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep, execute_at=None)

    result = s["orchestration_service"].process("task-1")

    assert len(result.audit_records) == len(result.change_result.results)
    for audit_record, action_result in zip(result.audit_records, result.change_result.results):
        assert audit_record.schedule_id == action_result.schedule_id
        assert audit_record.action == action_result.action
        assert audit_record.status == action_result.status
        # Independently retrievable through Commit #12's own read path.
        stored = s["audit_service"].get("task-1", action_result.schedule_id)
        assert audit_record in stored


# --- recovery execution never triggered ------------------------------------------------------------------


def test_recovery_execution_never_triggered():
    # Dependency already resolved before the schedule is ever created,
    # and due immediately (execute_at=None) -- a stable no_op
    # classification (unlike revalidate, never sensitive to being
    # observed twice in quick succession), whose OWN schedule_id is
    # already dispatchable the moment process() finishes.
    s = _stack()
    dep = _task(s["lifecycle_service"])
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    schedule = _task_with_schedule(s, "task-1", dep, execute_at=None)

    result = s["orchestration_service"].process("task-1")

    assert s["dispatch_service"].list("task-1") == []
    assert result.applied_actions[0].action == ACTION_NO_OP
    validation = s["validation_service"].validate("task-1", schedule.schedule_id)
    assert validation.valid is True
    dispatched = s["dispatch_service"].dispatch("task-1", schedule.schedule_id)
    assert dispatched.status == "dispatched"


# --- argument validation ------------------------------------------------------------------------------------


def test_process_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangeOrchestrationError):
        s["orchestration_service"].process("")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyChangeOrchestrationError):
        s["orchestration_service"].process("task-1", dependency_id="")


def test_process_handles_task_with_no_schedules():
    s = _stack()
    s["lifecycle_service"].create(_definition(task_id="task-1"))

    result = s["orchestration_service"].process("task-1")

    assert result.affected_schedule_ids == ()
    assert result.planned_actions == ()
    assert result.applied_actions == ()
    assert result.failures == ()
    assert result.audit_records == ()
