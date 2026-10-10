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
    ESCALATION_REQUIRED,
    NO_IMPACT,
    REVALIDATION_REQUIRED,
    SCHEDULE_NO_LONGER_VIABLE,
    WAITING_REQUIRED,
    InvalidAgentTaskRecoveryScheduleDependencyImpactError,
    LLMAgentTaskRecoveryPreflightScheduleDependencyImpactService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyService,
    LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService,
)
from backend.agent_task_recovery_scheduling import (
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

    lifecycle_service = LLMAgentTaskLifecycleService()
    dependency_service = LLMAgentTaskDependencyService(lifecycle_service)
    dependency_resolver = LLMAgentTaskDependencyResolver(lifecycle_service, dependency_service)
    gate_service = LLMAgentTaskRecoveryPreflightScheduleDependencyService(
        scheduling_service=scheduling_service, dependency_resolver=dependency_resolver
    )
    reconciliation_service = LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService(
        scheduling_service=scheduling_service, dependency_service=gate_service, dependency_resolver=dependency_resolver
    )
    timeout_service = LLMAgentTaskRecoveryPreflightScheduleDependencyTimeoutService(
        dependency_service=gate_service, scheduling_service=scheduling_service, max_wait_duration=timedelta(hours=1),
    )
    impact_service = LLMAgentTaskRecoveryPreflightScheduleDependencyImpactService(
        reconciliation_service=reconciliation_service, scheduling_service=scheduling_service,
        timeout_service=timeout_service,
    )
    impact_service_no_timeout = LLMAgentTaskRecoveryPreflightScheduleDependencyImpactService(
        reconciliation_service=reconciliation_service, scheduling_service=scheduling_service,
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
        "timeout_service": timeout_service,
        "impact_service": impact_service,
        "impact_service_no_timeout": impact_service_no_timeout,
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


# --- no impact -----------------------------------------------------------------------------


def test_no_impact_when_ready_and_unchanged():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    schedule = _task_with_schedule(s, "task-1", dep)

    s["impact_service"].analyze_schedule("task-1", schedule.schedule_id)  # baseline reconciliation
    outcome = s["impact_service"].analyze_schedule("task-1", schedule.schedule_id)

    assert outcome.category == NO_IMPACT
    assert outcome.evidence_sufficient is True
    assert outcome.changes == ()


# --- revalidation required -------------------------------------------------------------------


def test_revalidation_required_when_dependency_resolves():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)

    s["impact_service"].analyze_schedule("task-1", schedule.schedule_id)  # baseline, still pending
    _advance_to(s["lifecycle_service"], dep, COMPLETED)
    outcome = s["impact_service"].analyze_schedule("task-1", schedule.schedule_id)

    assert outcome.category == REVALIDATION_REQUIRED
    assert outcome.dependency_state == "ready"
    assert outcome.changes != ()


# --- waiting required --------------------------------------------------------------------------


def test_waiting_required_when_blocked_and_not_timed_out():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)

    outcome = s["impact_service"].analyze_schedule("task-1", schedule.schedule_id)

    assert outcome.category == WAITING_REQUIRED
    assert outcome.dependency_state == "blocked"


def test_waiting_required_without_timeout_service_configured():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    # No timeout_service wired at all -- can never distinguish
    # escalation-worthy from merely waiting, so it always reports
    # waiting_required.
    outcome = s["impact_service_no_timeout"].analyze_schedule("task-1", schedule.schedule_id, now=far_future)

    assert outcome.category == WAITING_REQUIRED


# --- escalation required -----------------------------------------------------------------------


def test_escalation_required_when_wait_exceeds_timeout_threshold():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    far_future = datetime.now(timezone.utc) + timedelta(hours=2)

    outcome = s["impact_service"].analyze_schedule("task-1", schedule.schedule_id, now=far_future)

    assert outcome.category == ESCALATION_REQUIRED
    assert "timeout threshold" in outcome.reason


# --- schedule no longer viable -------------------------------------------------------------------


def test_schedule_no_longer_viable_when_cancelled():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    s["scheduling_service"].cancel("task-1", schedule.schedule_id, reason="no longer needed")

    outcome = s["impact_service"].analyze_schedule("task-1", schedule.schedule_id)

    assert outcome.category == SCHEDULE_NO_LONGER_VIABLE
    assert "cancelled" in outcome.reason


def test_schedule_no_longer_viable_when_unauthorized():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    s["authorization_service"].revoke("task-1", schedule.authorization_id, reason="revoked externally")

    outcome = s["impact_service"].analyze_schedule("task-1", schedule.schedule_id)

    assert outcome.category == SCHEDULE_NO_LONGER_VIABLE
    assert "not currently authorized" in outcome.reason


def test_schedule_no_longer_viable_when_dependency_failed():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)
    _advance_to(s["lifecycle_service"], dep, FAILED)

    outcome = s["impact_service"].analyze_schedule("task-1", schedule.schedule_id)

    assert outcome.category == SCHEDULE_NO_LONGER_VIABLE
    assert outcome.dependency_state == "failed"


# --- insufficient evidence ------------------------------------------------------------------------


def test_no_category_inferred_when_evidence_is_insufficient():
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

    outcome = impact_service.analyze_schedule("task-1", schedule.schedule_id)

    assert outcome.category is None
    assert outcome.evidence_sufficient is False
    assert "could not be determined reliably" in outcome.reason


# --- multiple affected schedules ------------------------------------------------------------------


def test_multiple_affected_schedules_across_tasks():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule_1 = _task_with_schedule(s, "task-1", dep)
    schedule_2 = _task_with_schedule(s, "task-2", dep)

    result_1 = s["impact_service"].analyze("task-1", dependency_id=dep.task_id)
    result_2 = s["impact_service"].analyze("task-2", dependency_id=dep.task_id)

    assert len(result_1.outcomes) == 1
    assert result_1.outcomes[0].schedule_id == schedule_1.schedule_id
    assert result_1.outcomes[0].dependency_id == dep.task_id
    assert len(result_2.outcomes) == 1
    assert result_2.outcomes[0].schedule_id == schedule_2.schedule_id


def test_dependency_id_filters_out_unrelated_schedules():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    _task_with_schedule(s, "task-1", dep)

    unrelated = s["impact_service"].analyze("task-1", dependency_id="some-other-dependency")
    matching = s["impact_service"].analyze("task-1", dependency_id=dep.task_id)

    assert unrelated.outcomes == ()
    assert len(matching.outcomes) == 1


def test_analyze_without_dependency_id_returns_every_schedule():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)

    result = s["impact_service"].analyze("task-1")

    assert len(result.outcomes) == 1
    assert result.outcomes[0].schedule_id == schedule.schedule_id
    assert result.dependency_id is None


# --- read-only / deterministic ----------------------------------------------------------------------


def test_analyze_never_mutates_schedule_or_task_state():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)

    s["impact_service"].analyze_schedule("task-1", schedule.schedule_id)

    assert s["scheduling_service"].get("task-1", schedule.schedule_id).status == "scheduled"
    assert s["lifecycle_service"].get(dep.task_id).current_state == "created"


def test_deterministic_repeated_analysis():
    s = _stack()
    dep = _task(s["lifecycle_service"])
    schedule = _task_with_schedule(s, "task-1", dep)

    first = s["impact_service"].analyze_schedule("task-1", schedule.schedule_id)
    second = s["impact_service"].analyze_schedule("task-1", schedule.schedule_id)

    assert first.category == second.category
    assert first.dependency_state == second.dependency_state
    assert first.reason == second.reason


# --- argument validation --------------------------------------------------------------------------


def test_analyze_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyImpactError):
        s["impact_service"].analyze("")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyImpactError):
        s["impact_service"].analyze("task-1", dependency_id="")
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyImpactError):
        s["impact_service"].analyze_schedule("task-1", "")


def test_analyze_schedule_rejects_unknown_schedule():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryScheduleDependencyImpactError):
        s["impact_service"].analyze_schedule("task-1", "never-existed")
