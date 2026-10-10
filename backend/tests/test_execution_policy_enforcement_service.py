from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionPolicy,
    ExecutionPolicyAssignmentService,
    ExecutionPolicyConflictService,
    ExecutionPolicyDecision,
    ExecutionPolicyEnforcementError as Error,
    ExecutionPolicyEnforcementService,
    ExecutionPolicyEvaluationService,
    ExecutionPolicyExceptionService,
    ExecutionPolicyService,
)


class _FakeSessionService:
    def __init__(self, actions_by_session):
        self._actions_by_session = actions_by_session

    def requested_actions(self, session_id):
        return self._actions_by_session.get(session_id, [])


def _build(actions_by_session=None):
    policy_service = ExecutionPolicyService()
    session_service = _FakeSessionService(actions_by_session or {})
    evaluation_service = ExecutionPolicyEvaluationService(policy_service, session_service)
    assignment_service = ExecutionPolicyAssignmentService(policy_service)
    conflict_service = ExecutionPolicyConflictService(policy_service)
    exception_service = ExecutionPolicyExceptionService(policy_service)
    enforcement_service = ExecutionPolicyEnforcementService(
        assignment_service,
        evaluation_service,
        conflict_service,
        exception_service,
    )
    return {
        "policy": policy_service,
        "evaluation": evaluation_service,
        "assignment": assignment_service,
        "conflict": conflict_service,
        "exception": exception_service,
        "enforcement": enforcement_service,
    }


def _register(policy_service, policy_id, rules=("read",)):
    return policy_service.register(
        ExecutionPolicy(
            policy_id=policy_id,
            name=policy_id,
            rules=frozenset(rules),
        )
    )


class TestExecutionPolicyEnforcementService:
    def test_allowed_execution(self):
        services = _build(actions_by_session={"session-1": ["read"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["assignment"].assign("policy-1", "session", "session-1")

        decision = services["enforcement"].authorize("session-1")

        assert isinstance(decision, ExecutionPolicyDecision)
        assert decision.allowed is True
        assert decision.violations == ()

    def test_policy_violation(self):
        services = _build(actions_by_session={"session-1": ["read", "delete"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["assignment"].assign("policy-1", "session", "session-1")

        decision = services["enforcement"].authorize("session-1")

        assert decision.allowed is False
        assert decision.violations == ("policy-1:unpermitted_action:delete",)

    def test_exception_override(self):
        services = _build(actions_by_session={"session-1": ["read", "delete"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["assignment"].assign("policy-1", "session", "session-1")

        services["exception"].create(
            "policy-1",
            "session-1",
            "delete",
            "approved for migration",
            datetime.now(timezone.utc) + timedelta(hours=1),
        )

        decision = services["enforcement"].authorize("session-1")

        assert decision.allowed is True
        assert decision.violations == ()

    def test_unresolved_conflict_blocks_execution(self):
        services = _build(actions_by_session={"session-1": ["read"]})
        _register(services["policy"], "policy-a", rules=("delete",))
        _register(services["policy"], "policy-b", rules=("!delete",))

        conflicts = services["conflict"].detect(["policy-a", "policy-b"], scope_id="session-1")

        decision = services["enforcement"].authorize("session-1")

        assert decision.allowed is False
        assert decision.violations == (f"unresolved_conflict:{conflicts[0].conflict_id}",)

    def test_conflict_resolution_unblocks_execution(self):
        services = _build(actions_by_session={"session-1": ["read"]})
        _register(services["policy"], "policy-a", rules=("delete",))
        _register(services["policy"], "policy-b", rules=("!delete",))

        conflicts = services["conflict"].detect(["policy-a", "policy-b"], scope_id="session-1")
        services["conflict"].resolve(conflicts[0].conflict_id, "policy-a wins")

        decision = services["enforcement"].authorize("session-1")

        assert decision.allowed is True

    def test_decision_history(self):
        services = _build(actions_by_session={"session-1": ["read"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["assignment"].assign("policy-1", "session", "session-1")

        first = services["enforcement"].authorize("session-1")
        second = services["enforcement"].deny("session-1")

        assert services["enforcement"].history("session-1") == [first, second]
        assert services["enforcement"].decision("session-1") == second

    def test_decision_unknown_session_is_an_error(self):
        services = _build()

        with pytest.raises(Error):
            services["enforcement"].decision("unknown-session")

    def test_deterministic_result(self):
        services = _build(actions_by_session={"session-1": ["read", "delete", "admin"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["assignment"].assign("policy-1", "session", "session-1")

        first = services["enforcement"].authorize("session-1")
        second = services["enforcement"].authorize("session-1")

        assert first.allowed == second.allowed
        assert first.violations == second.violations
