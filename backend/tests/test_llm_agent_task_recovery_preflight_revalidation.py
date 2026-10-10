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
    InvalidAgentTaskRecoveryPreflightRevalidationError,
    LLMAgentTaskRecoveryGuardEvaluationService,
    LLMAgentTaskRecoveryGuardService,
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
    return {
        "event_service": event_service,
        "classifier": classifier,
        "replay_service": replay_service,
        "readiness": readiness,
        "preflight_service": preflight_service,
        "preflight_store": preflight_store,
        "invalidation_service": invalidation_service,
        "revalidation_service": revalidation_service,
    }


def _fail_task(event_service, task_id="task-1"):
    event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": PLANNED})
    return event_service.emit(task_id, LIFECYCLE_TRANSITIONED, payload={"to_state": FAILED})


# --- fresh preflight requires no rebuild --------------------------------------------------------------


def test_fresh_preflight_requires_no_rebuild():
    s = _stack()
    _fail_task(s["event_service"])
    original = s["preflight_store"].save(s["preflight_service"].run("task-1"))

    result = s["revalidation_service"].revalidate("task-1")

    assert result.was_revalidated is False
    assert result.previous_preflight_id == original.preflight_id
    assert result.current_preflight_id == original.preflight_id
    assert result.decision == original.decision
    assert result.stale_reasons == ()
    assert len(s["preflight_store"].history("task-1")) == 1


def test_revalidate_rejects_blank_task_id():
    s = _stack()
    with pytest.raises(InvalidAgentTaskRecoveryPreflightRevalidationError):
        s["revalidation_service"].revalidate("")


def test_revalidate_no_prior_preflight_builds_one():
    s = _stack()
    _fail_task(s["event_service"])

    result = s["revalidation_service"].revalidate("task-1")

    assert result.was_revalidated is True
    assert result.previous_preflight_id is None
    assert result.current_preflight_id is not None
    assert "no stored preflight existed" in result.stale_reasons[0]


# --- stale preflight produces a new decision --------------------------------------------------------------


def test_stale_preflight_produces_a_new_decision():
    s = _stack()
    failure = _fail_task(s["event_service"])
    stale_plan = AgentTaskFailureRecoveryPlan(
        task_id="task-1", failure_event_id="a-different-failure-id", failure_category="execution",
        recommended_action=RECOVERY_ACTION_RETRY, reason="stale", priority=3, blocking_conditions=(),
    )
    from backend.agent_task_recovery_guardrails import AgentTaskRecoveryPreflightResult
    from datetime import datetime, timezone

    original = s["preflight_store"].save(
        AgentTaskRecoveryPreflightResult(
            task_id="task-1", plan=stale_plan, guard_result=None, decision=ALLOW,
            blocking_reasons=(), warnings=(), checked_at=datetime.now(timezone.utc),
        )
    )

    result = s["revalidation_service"].revalidate("task-1")

    assert result.was_revalidated is True
    assert result.previous_preflight_id == original.preflight_id
    assert result.current_preflight_id != original.preflight_id
    assert any("failure_event_id" in reason for reason in result.stale_reasons)


# --- invalid preflight is replaced, not revived --------------------------------------------------------------


def test_explicitly_invalidated_preflight_is_replaced_not_revived():
    s = _stack()
    _fail_task(s["event_service"])
    original = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    assert original.decision == ALLOW  # confirm it would otherwise still look fresh

    s["invalidation_service"].invalidate("task-1", reason="operator flagged this manually")
    # Conditions ALSO genuinely change (not required for "not revived" to
    # hold, but needed here so the rebuilt content is distinguishable from
    # the invalidated original rather than colliding with Commit #4's own
    # content-based idempotency on identical content).
    s["readiness"].set(policy_passed=False)

    result = s["revalidation_service"].revalidate("task-1")

    assert result.was_revalidated is True
    assert result.previous_preflight_id == original.preflight_id
    assert result.current_preflight_id != original.preflight_id
    assert result.decision == DENY
    assert result.stale_reasons == ("operator flagged this manually",)


# --- previous/current IDs are linked --------------------------------------------------------------


def test_previous_and_current_ids_are_linked():
    s = _stack()
    _fail_task(s["event_service"])
    original = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["invalidation_service"].invalidate("task-1", reason="linkage check")
    s["readiness"].set(policy_passed=False)

    result = s["revalidation_service"].revalidate("task-1")

    assert result.previous_preflight_id == original.preflight_id
    new_record = s["preflight_store"].get("task-1")
    assert result.current_preflight_id == new_record.preflight_id
    assert new_record.preflight_id != original.preflight_id


def test_revalidate_with_given_preflight_id_matching_current_succeeds():
    s = _stack()
    _fail_task(s["event_service"])
    original = s["preflight_store"].save(s["preflight_service"].run("task-1"))

    result = s["revalidation_service"].revalidate("task-1", preflight_id=original.preflight_id)

    assert result.was_revalidated is False
    assert result.current_preflight_id == original.preflight_id


def test_revalidate_with_stale_given_preflight_id_raises():
    s = _stack()
    _fail_task(s["event_service"])
    s["preflight_store"].save(s["preflight_service"].run("task-1"))

    with pytest.raises(InvalidAgentTaskRecoveryPreflightRevalidationError):
        s["revalidation_service"].revalidate("task-1", preflight_id="not-the-current-one")


# --- new decision reflects current task conditions --------------------------------------------------------------


def test_new_decision_reflects_current_task_conditions():
    s = _stack()
    _fail_task(s["event_service"])
    original = s["preflight_store"].save(s["preflight_service"].run("task-1"))
    assert original.decision == ALLOW

    s["invalidation_service"].invalidate("task-1", reason="forcing a rebuild")
    # Current conditions change: policy now denies (the SAME fake instance
    # every collaborator in this stack already shares, so no service needs
    # to be re-wired to observe the change).
    s["readiness"].set(policy_passed=False)

    result = s["revalidation_service"].revalidate("task-1")

    assert result.was_revalidated is True
    assert result.decision == DENY


# --- repeated revalidation is idempotent --------------------------------------------------------------


def test_repeated_revalidation_is_idempotent():
    s = _stack()
    _fail_task(s["event_service"])
    s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["invalidation_service"].invalidate("task-1", reason="force one rebuild")
    # Conditions ALSO genuinely change, so the rebuilt preflight is
    # distinguishable from the invalidated original -- otherwise Commit
    # #4's own content-based idempotency would keep resolving back to the
    # SAME (still-invalidated) preflight_id on every call, and "was
    # revalidated" would never settle to False.
    s["readiness"].set(policy_passed=False)

    first = s["revalidation_service"].revalidate("task-1")
    second = s["revalidation_service"].revalidate("task-1")

    assert first.was_revalidated is True
    assert second.was_revalidated is False
    assert second.previous_preflight_id == first.current_preflight_id
    assert second.current_preflight_id == first.current_preflight_id
    assert len(s["preflight_store"].history("task-1")) == 2  # original + one rebuild, never a third


# --- no recovery/task mutation occurs --------------------------------------------------------------


def test_no_task_state_mutation_occurs():
    s = _stack()
    _fail_task(s["event_service"])
    s["preflight_store"].save(s["preflight_service"].run("task-1"))
    s["invalidation_service"].invalidate("task-1", reason="force a rebuild")

    before_classification = s["classifier"].classify("task-1")
    before_replay = s["replay_service"].replay("task-1")

    s["revalidation_service"].revalidate("task-1")

    after_classification = s["classifier"].classify("task-1")
    after_replay = s["replay_service"].replay("task-1")

    assert before_classification == after_classification
    assert before_replay == after_replay
