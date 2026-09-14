from datetime import datetime, timezone

import pytest

from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_task_event_analytics import (
    RECOVERY_ACTION_RETRY,
    AgentTaskFailureRecoveryPlan,
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
from backend.agent_task_lifecycle import FAILED, PLANNED
from backend.agent_task_queue_retry_eligibility import RetryEligibilityResult
from backend.agent_task_readiness import AgentTaskReadinessCheck, AgentTaskReadinessResult
from backend.agent_task_recovery_guardrails import (
    APPROVED,
    PENDING,
    REJECTED,
    AgentTaskRecoveryPreflightResult,
    InvalidAgentTaskRecoveryPreflightApprovalError,
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryGuardService,
    LLMAgentTaskRecoveryPreflightApprovalService,
    LLMAgentTaskRecoveryPreflightFreshnessService,
    LLMAgentTaskRecoveryPreflightInvalidationService,
    LLMAgentTaskRecoveryPreflightRevalidationService,
    LLMAgentTaskRecoveryPreflightService,
    LLMAgentTaskRecoveryPreflightStore,
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


def _stack(readiness=None, retry_eligibility=None):
    store = InMemoryAgentTaskEventStore()
    event_service = LLMAgentTaskEventService(store=store)
    query_service = LLMAgentTaskEventQueryService(store=store)
    classifier = LLMAgentTaskEventFailureClassifier(query_service=query_service)
    replay_service = LLMAgentTaskEventReplayService(query_service=query_service)

    readiness = readiness if readiness is not None else _FakeReadinessService()
    retry_eligibility = retry_eligibility if retry_eligibility is not None else _FakeRetryEligibilityService()

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
    revalidation_service = LLMAgentTaskRecoveryPreflightRevalidationService(
        preflight_store=preflight_store, preflight_service=preflight_service, invalidation_service=invalidation_service
    )
    approval_service = LLMAgentTaskRecoveryPreflightApprovalService(
        preflight_store=preflight_store, invalidation_service=invalidation_service
    )
    return {
        "event_service": event_service,
        "classifier": classifier,
        "replay_service": replay_service,
        "readiness": readiness,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "invalidation_service": invalidation_service,
        "revalidation_service": revalidation_service,
        "approval_service": approval_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


# --- request creates pending approval --------------------------------------------------------------


def test_request_creates_pending_approval():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    assert preflight.decision == ALLOW

    approval = s["approval_service"].request("task-1", preflight.preflight_id)

    assert approval.status == PENDING
    assert approval.task_id == "task-1"
    assert approval.preflight_id == preflight.preflight_id
    assert approval.actor is None
    assert approval.resolved_at is None
    assert s["approval_service"].status("task-1", preflight.preflight_id) == PENDING


def test_request_rejects_blank_arguments():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightApprovalError):
        s["approval_service"].request("", "some-id")
    with pytest.raises(InvalidAgentTaskRecoveryPreflightApprovalError):
        s["approval_service"].request("task-1", "")


def test_request_unknown_preflight_raises():
    s = _stack()
    _fail_task(s["event_service"])
    s["preflight_store"].save(s["preflight_service"].run("task-1"))

    with pytest.raises(InvalidAgentTaskRecoveryPreflightApprovalError):
        s["approval_service"].request("task-1", "never-existed")


def test_request_non_allow_preflight_raises():
    s = _stack()
    _fail_task(s["event_service"])
    s["readiness"].set(policy_passed=False)
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    assert preflight.decision == DENY

    with pytest.raises(InvalidAgentTaskRecoveryPreflightApprovalError):
        s["approval_service"].request("task-1", preflight.preflight_id)


def test_get_and_status_are_none_for_unrequested_preflight():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))

    assert s["approval_service"].get("task-1", preflight.preflight_id) is None
    assert s["approval_service"].status("task-1", preflight.preflight_id) is None


# --- valid preflight can be approved --------------------------------------------------------------


def test_valid_preflight_can_be_approved():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)

    approval = s["approval_service"].approve("task-1", preflight.preflight_id, actor="alice")

    assert approval.status == APPROVED
    assert approval.actor == "alice"
    assert approval.resolved_at is not None
    assert s["approval_service"].status("task-1", preflight.preflight_id) == APPROVED


def test_approve_without_prior_request_raises():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))

    with pytest.raises(InvalidAgentTaskRecoveryPreflightApprovalError):
        s["approval_service"].approve("task-1", preflight.preflight_id, actor="alice")


# --- invalid/stale/superseded preflight cannot be approved --------------------------------------------------------------


def test_superseded_preflight_cannot_be_approved():
    s = _stack()
    _fail_task(s["event_service"])
    old_preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", old_preflight.preflight_id)

    # A newer preflight now supersedes it.
    stale_plan = AgentTaskFailureRecoveryPlan(
        task_id="task-1", failure_event_id="a-different-failure-id", failure_category="execution",
        recommended_action=RECOVERY_ACTION_RETRY, reason="different", priority=3, blocking_conditions=(),
    )
    s["preflight_store"].save(
        AgentTaskRecoveryPreflightResult(
            task_id="task-1", plan=stale_plan, guard_result=None, decision=ALLOW,
            blocking_reasons=(), warnings=(), checked_at=datetime.now(timezone.utc),
        )
    )

    with pytest.raises(InvalidAgentTaskRecoveryPreflightApprovalError):
        s["approval_service"].approve("task-1", old_preflight.preflight_id, actor="alice")


def test_invalidated_preflight_cannot_be_approved():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)

    s["invalidation_service"].invalidate("task-1", reason="operator flagged this")

    with pytest.raises(InvalidAgentTaskRecoveryPreflightApprovalError):
        s["approval_service"].approve("task-1", preflight.preflight_id, actor="alice")


def test_stale_preflight_cannot_be_approved():
    s = _stack()
    failure = _fail_task(s["event_service"])
    stale_plan = AgentTaskFailureRecoveryPlan(
        task_id="task-1", failure_event_id="a-different-failure-id", failure_category="execution",
        recommended_action=RECOVERY_ACTION_RETRY, reason="stale", priority=3, blocking_conditions=(),
    )
    preflight = s["preflight_store"].save(
        AgentTaskRecoveryPreflightResult(
            task_id="task-1", plan=stale_plan, guard_result=None, decision=ALLOW,
            blocking_reasons=(), warnings=(), checked_at=datetime.now(timezone.utc),
        )
    )

    with pytest.raises(InvalidAgentTaskRecoveryPreflightApprovalError):
        s["approval_service"].request("task-1", preflight.preflight_id)


# --- rejection records reason --------------------------------------------------------------


def test_rejection_records_reason():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)

    approval = s["approval_service"].reject("task-1", preflight.preflight_id, actor="bob", reason="not needed anymore")

    assert approval.status == REJECTED
    assert approval.reason == "not needed anymore"
    assert approval.actor == "bob"


def test_reject_requires_reason():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightApprovalError):
        s["approval_service"].reject("task-1", preflight.preflight_id, actor="bob", reason="")


# --- already-approved/rejected transitions behave deterministically --------------------------------------------------------------


def test_repeated_approve_is_idempotent():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)

    first = s["approval_service"].approve("task-1", preflight.preflight_id, actor="alice")
    second = s["approval_service"].approve("task-1", preflight.preflight_id, actor="someone-else")

    assert first == second
    assert second.actor == "alice"


def test_repeated_reject_is_idempotent():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)

    first = s["approval_service"].reject("task-1", preflight.preflight_id, actor="bob", reason="first reason")
    second = s["approval_service"].reject("task-1", preflight.preflight_id, actor="carol", reason="second reason")

    assert first == second
    assert second.reason == "first reason"


def test_approve_after_reject_raises():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)
    s["approval_service"].reject("task-1", preflight.preflight_id, actor="bob", reason="no")

    with pytest.raises(InvalidAgentTaskRecoveryPreflightApprovalError):
        s["approval_service"].approve("task-1", preflight.preflight_id, actor="alice")


def test_reject_after_approve_raises():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)
    s["approval_service"].approve("task-1", preflight.preflight_id, actor="alice")

    with pytest.raises(InvalidAgentTaskRecoveryPreflightApprovalError):
        s["approval_service"].reject("task-1", preflight.preflight_id, actor="bob", reason="too late")


def test_repeated_request_after_resolution_does_not_reopen():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)
    s["approval_service"].reject("task-1", preflight.preflight_id, actor="bob", reason="no")

    reopened = s["approval_service"].request("task-1", preflight.preflight_id)

    assert reopened.status == REJECTED
    assert reopened.reason == "no"


# --- approval history is preserved --------------------------------------------------------------


def test_approval_history_is_preserved_for_multiple_preflights():
    s = _stack()
    _fail_task(s["event_service"])
    first_preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", first_preflight.preflight_id)
    s["approval_service"].reject("task-1", first_preflight.preflight_id, actor="bob", reason="no")

    # A genuinely distinct second preflight for the same task (content
    # differs from the first, so Commit #4's own content-based
    # idempotency mints a real, separate preflight_id rather than
    # resolving back to the rejected one).
    second_plan = AgentTaskFailureRecoveryPlan(
        task_id="task-1", failure_event_id=first_preflight.plan.failure_event_id,
        failure_category=first_preflight.plan.failure_category,
        recommended_action=RECOVERY_ACTION_RETRY, reason="re-evaluated after reconsideration",
        priority=3, blocking_conditions=(),
    )
    second_preflight = s["preflight_store"].save(
        AgentTaskRecoveryPreflightResult(
            task_id="task-1", plan=second_plan, guard_result=None, decision=ALLOW,
            blocking_reasons=(), warnings=(), checked_at=datetime.now(timezone.utc),
        )
    )
    assert second_preflight.preflight_id != first_preflight.preflight_id

    s["approval_service"].request("task-1", second_preflight.preflight_id)
    s["approval_service"].approve("task-1", second_preflight.preflight_id, actor="alice")

    first_record = s["approval_service"].get("task-1", first_preflight.preflight_id)
    second_record = s["approval_service"].get("task-1", second_preflight.preflight_id)

    assert first_record.status == REJECTED
    assert first_record.reason == "no"
    assert second_record.status == APPROVED
    assert second_record.actor == "alice"


# --- actor/reference metadata persists --------------------------------------------------------------


def test_actor_metadata_persists_across_reads():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)
    s["approval_service"].approve("task-1", preflight.preflight_id, actor="reviewer-42")

    fetched = s["approval_service"].get("task-1", preflight.preflight_id)

    assert fetched.actor == "reviewer-42"


def test_authorized_callable_can_reject_an_actor():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    approval_service = LLMAgentTaskRecoveryPreflightApprovalService(
        preflight_store=s["preflight_store"], invalidation_service=s["invalidation_service"],
        authorized=lambda actor, task_id: actor == "trusted-reviewer",
    )
    approval_service.request("task-1", preflight.preflight_id)

    with pytest.raises(InvalidAgentTaskRecoveryPreflightApprovalError):
        approval_service.approve("task-1", preflight.preflight_id, actor="random-person")

    approved = approval_service.approve("task-1", preflight.preflight_id, actor="trusted-reviewer")
    assert approved.status == APPROVED


# --- approval is tied to the exact preflight version --------------------------------------------------------------


def test_approval_is_scoped_to_exact_preflight_id():
    s = _stack()
    _fail_task(s["event_service"])
    first_preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", first_preflight.preflight_id)
    s["approval_service"].approve("task-1", first_preflight.preflight_id, actor="alice")

    s["readiness"].set(policy_passed=False)
    s["invalidation_service"].invalidate("task-1", reason="force rebuild")
    revalidation = s["revalidation_service"].revalidate("task-1")
    new_preflight_id = revalidation.current_preflight_id
    assert new_preflight_id != first_preflight.preflight_id

    assert s["approval_service"].status("task-1", first_preflight.preflight_id) == APPROVED
    assert s["approval_service"].status("task-1", new_preflight_id) is None


# --- revalidated replacement requires its own approval --------------------------------------------------------------


def test_revalidated_replacement_requires_its_own_approval():
    s = _stack()
    _fail_task(s["event_service"])
    first_preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", first_preflight.preflight_id)
    s["approval_service"].approve("task-1", first_preflight.preflight_id, actor="alice")

    s["readiness"].set(policy_passed=False)
    s["invalidation_service"].invalidate("task-1", reason="force rebuild")
    revalidation = s["revalidation_service"].revalidate("task-1")
    new_preflight_id = revalidation.current_preflight_id
    assert revalidation.decision == DENY

    # The new one cannot simply inherit the old approval, and cannot even
    # be requested since it is not ALLOW.
    with pytest.raises(InvalidAgentTaskRecoveryPreflightApprovalError):
        s["approval_service"].request("task-1", new_preflight_id)


# --- no recovery execution occurs --------------------------------------------------------------


def test_no_task_state_mutation_occurs():
    s = _stack()
    _fail_task(s["event_service"])
    preflight = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["approval_service"].request("task-1", preflight.preflight_id)

    before_classification = s["classifier"].classify("task-1")
    before_replay = s["replay_service"].replay("task-1")

    s["approval_service"].approve("task-1", preflight.preflight_id, actor="alice")

    after_classification = s["classifier"].classify("task-1")
    after_replay = s["replay_service"].replay("task-1")

    assert before_classification == after_classification
    assert before_replay == after_replay
