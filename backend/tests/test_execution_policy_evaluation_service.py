import pytest

from backend.session import (
    ExecutionPolicy,
    ExecutionPolicyError,
    ExecutionPolicyEvaluation,
    ExecutionPolicyEvaluationError as Error,
    ExecutionPolicyEvaluationService,
    ExecutionPolicyService,
)


class _FakeSessionService:
    def __init__(self, actions_by_session):
        self._actions_by_session = actions_by_session

    def requested_actions(self, session_id):
        if session_id not in self._actions_by_session:
            raise KeyError(session_id)

        return self._actions_by_session[session_id]


def _build(actions_by_session=None):
    policy_service = ExecutionPolicyService()
    session_service = _FakeSessionService(actions_by_session or {})
    evaluation_service = ExecutionPolicyEvaluationService(policy_service, session_service)
    return policy_service, session_service, evaluation_service


def _register_policy(policy_service, policy_id="policy-1", rules=("read", "write"), enabled=True):
    return policy_service.register(
        ExecutionPolicy(
            policy_id=policy_id,
            name="default-policy",
            rules=frozenset(rules),
            enabled=enabled,
        )
    )


class TestExecutionPolicyEvaluationService:
    def test_allowed_session(self):
        policy_service, _session_service, evaluation_service = _build(
            actions_by_session={"session-1": ["read"]}
        )
        _register_policy(policy_service)

        evaluation = evaluation_service.evaluate("policy-1", "session-1")

        assert isinstance(evaluation, ExecutionPolicyEvaluation)
        assert evaluation.allowed is True
        assert evaluation.violations == ()

    def test_rule_violation(self):
        policy_service, _session_service, evaluation_service = _build(
            actions_by_session={"session-1": ["read", "delete"]}
        )
        _register_policy(policy_service)

        evaluation = evaluation_service.evaluate("policy-1", "session-1")

        assert evaluation.allowed is False
        assert evaluation.violations == ("unpermitted_action:delete",)

    def test_multiple_violations(self):
        policy_service, _session_service, evaluation_service = _build(
            actions_by_session={"session-1": ["read", "delete", "admin"]}
        )
        _register_policy(policy_service)

        evaluation = evaluation_service.evaluate("policy-1", "session-1")

        assert evaluation.allowed is False
        assert evaluation.violations == (
            "unpermitted_action:admin",
            "unpermitted_action:delete",
        )

    def test_disabled_policy(self):
        policy_service, _session_service, evaluation_service = _build(
            actions_by_session={"session-1": ["read"]}
        )
        _register_policy(policy_service, enabled=False)

        evaluation = evaluation_service.evaluate("policy-1", "session-1")

        assert evaluation.allowed is False
        assert evaluation.violations == ("policy_disabled",)

    def test_evaluation_history(self):
        policy_service, _session_service, evaluation_service = _build(
            actions_by_session={"session-1": ["read"], "session-2": ["read"]}
        )
        _register_policy(policy_service)

        first = evaluation_service.evaluate("policy-1", "session-1")
        second = evaluation_service.evaluate("policy-1", "session-1")
        evaluation_service.evaluate("policy-1", "session-2")

        assert evaluation_service.history("session-1") == [first, second]

    def test_violations_is_read_only(self):
        policy_service, _session_service, evaluation_service = _build(
            actions_by_session={"session-1": ["read", "delete"]}
        )
        _register_policy(policy_service)

        result = evaluation_service.violations("policy-1", "session-1")

        assert result == ["unpermitted_action:delete"]
        assert evaluation_service.history("session-1") == []

    def test_unknown_policy_is_an_error(self):
        _policy_service, _session_service, evaluation_service = _build(
            actions_by_session={"session-1": ["read"]}
        )

        with pytest.raises(ExecutionPolicyError):
            evaluation_service.evaluate("unknown-policy", "session-1")

    def test_unknown_session_is_an_error(self):
        policy_service, _session_service, evaluation_service = _build()
        _register_policy(policy_service)

        with pytest.raises(KeyError):
            evaluation_service.evaluate("policy-1", "unknown-session")

    def test_evaluate_rejects_blank_ids(self):
        _policy_service, _session_service, evaluation_service = _build()

        with pytest.raises(Error):
            evaluation_service.evaluate("", "session-1")

        with pytest.raises(Error):
            evaluation_service.evaluate("policy-1", "")
