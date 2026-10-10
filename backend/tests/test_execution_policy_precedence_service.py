import pytest

from backend.session import (
    ExecutionPolicy,
    ExecutionPolicyAssignmentService,
    ExecutionPolicyPrecedence,
    ExecutionPolicyPrecedenceError as Error,
    ExecutionPolicyPrecedenceService,
    ExecutionPolicyService,
)


def _register_policy(policy_service, policy_id):
    return policy_service.register(
        ExecutionPolicy(
            policy_id=policy_id,
            name=policy_id,
            rules=frozenset({"read"}),
        )
    )


def _build():
    policy_service = ExecutionPolicyService()
    assignment_service = ExecutionPolicyAssignmentService(policy_service)
    precedence_service = ExecutionPolicyPrecedenceService(assignment_service)
    return policy_service, assignment_service, precedence_service


class TestExecutionPolicyPrecedenceService:
    def test_precedence_ordering_overrides_numeric_priority(self):
        _policy_service, _assignment_service, precedence_service = _build()

        rule = precedence_service.set("policy-a", "policy-b")

        assert isinstance(rule, ExecutionPolicyPrecedence)
        assert precedence_service.resolve(["policy-b", "policy-a"]) == ["policy-a", "policy-b"]

    def test_numeric_fallback_when_no_rule_is_set(self):
        _policy_service, _assignment_service, precedence_service = _build()

        assert precedence_service.resolve(["policy-a", "policy-b"]) == ["policy-a", "policy-b"]

    def test_cycle_detection(self):
        _policy_service, _assignment_service, precedence_service = _build()
        precedence_service.set("policy-a", "policy-b")

        with pytest.raises(Error):
            precedence_service.set("policy-b", "policy-a")

    def test_transitive_cycle_detection(self):
        _policy_service, _assignment_service, precedence_service = _build()
        precedence_service.set("policy-a", "policy-b")
        precedence_service.set("policy-b", "policy-c")

        with pytest.raises(Error):
            precedence_service.set("policy-c", "policy-a")

    def test_self_precedence_rejection(self):
        _policy_service, _assignment_service, precedence_service = _build()

        with pytest.raises(Error):
            precedence_service.set("policy-a", "policy-a")

    def test_conflicting_policies(self):
        _policy_service, _assignment_service, precedence_service = _build()

        conflicts = precedence_service.conflicts(["policy-a", "policy-b", "policy-c"])

        assert conflicts == [
            ("policy-a", "policy-b"),
            ("policy-a", "policy-c"),
            ("policy-b", "policy-c"),
        ]

    def test_explicit_rule_removes_pair_from_conflicts(self):
        _policy_service, _assignment_service, precedence_service = _build()
        precedence_service.set("policy-a", "policy-b")

        conflicts = precedence_service.conflicts(["policy-a", "policy-b", "policy-c"])

        assert conflicts == [
            ("policy-a", "policy-c"),
            ("policy-b", "policy-c"),
        ]

    def test_order_resolves_scope_with_precedence_override(self):
        policy_service, assignment_service, precedence_service = _build()
        _register_policy(policy_service, "policy-a")
        _register_policy(policy_service, "policy-b")

        assignment_service.assign("policy-a", "session", "session-1", priority=1)
        assignment_service.assign("policy-b", "session", "session-1", priority=10)

        assert precedence_service.order("session-1") == ["policy-b", "policy-a"]

        precedence_service.set("policy-a", "policy-b")

        assert precedence_service.order("session-1") == ["policy-a", "policy-b"]

    def test_order_rejects_blank_scope_id(self):
        _policy_service, _assignment_service, precedence_service = _build()

        with pytest.raises(Error):
            precedence_service.order("")
