import pytest

from backend.session import (
    ExecutionPolicy,
    ExecutionPolicyAssignment,
    ExecutionPolicyAssignmentError as Error,
    ExecutionPolicyAssignmentService,
    ExecutionPolicyError,
    ExecutionPolicyService,
)


def _build():
    policy_service = ExecutionPolicyService()
    assignment_service = ExecutionPolicyAssignmentService(policy_service)
    return policy_service, assignment_service


def _register_policy(policy_service, policy_id, rules=("read",), enabled=True):
    return policy_service.register(
        ExecutionPolicy(
            policy_id=policy_id,
            name=policy_id,
            rules=frozenset(rules),
            enabled=enabled,
        )
    )


class TestExecutionPolicyAssignmentService:
    def test_assign_and_remove(self):
        policy_service, assignment_service = _build()
        _register_policy(policy_service, "policy-1")

        assignment = assignment_service.assign("policy-1", "session", "session-1")

        assert isinstance(assignment, ExecutionPolicyAssignment)
        assert [policy.policy_id for policy in assignment_service.policies("session", "session-1")] == ["policy-1"]

        removed = assignment_service.remove(assignment.assignment_id)

        assert removed == assignment
        assert assignment_service.policies("session", "session-1") == []

    def test_remove_unknown_assignment_is_an_error(self):
        _policy_service, assignment_service = _build()

        with pytest.raises(Error):
            assignment_service.remove("unknown-assignment")

    def test_priority_resolution(self):
        policy_service, assignment_service = _build()
        _register_policy(policy_service, "policy-low")
        _register_policy(policy_service, "policy-high")

        assignment_service.assign("policy-low", "session", "session-1", priority=1)
        assignment_service.assign("policy-high", "session", "session-1", priority=10)

        policies = assignment_service.policies("session", "session-1")

        assert [policy.policy_id for policy in policies] == ["policy-high", "policy-low"]

    def test_disabled_policy_is_ignored(self):
        policy_service, assignment_service = _build()
        _register_policy(policy_service, "policy-1")

        assignment_service.assign("policy-1", "session", "session-1")
        policy_service.disable("policy-1")

        assert assignment_service.policies("session", "session-1") == []
        assert assignment_service.resolve("session-1") == []

    def test_duplicate_assignment_is_rejected(self):
        policy_service, assignment_service = _build()
        _register_policy(policy_service, "policy-1")

        assignment_service.assign("policy-1", "session", "session-1")

        with pytest.raises(Error):
            assignment_service.assign("policy-1", "session", "session-1")

    def test_assign_unknown_policy_is_an_error(self):
        _policy_service, assignment_service = _build()

        with pytest.raises(ExecutionPolicyError):
            assignment_service.assign("unknown-policy", "session", "session-1")

    def test_inherited_policy_resolution(self):
        policy_service, assignment_service = _build()
        _register_policy(policy_service, "session-policy")
        _register_policy(policy_service, "workspace-policy")
        _register_policy(policy_service, "scope-policy")

        assignment_service.assign("workspace-policy", "workspace", "scope-1", priority=5)
        assignment_service.assign("scope-policy", "execution_scope", "scope-1", priority=5)
        assignment_service.assign("session-policy", "session", "scope-1", priority=5)

        resolved = assignment_service.resolve("scope-1")

        assert [policy.policy_id for policy in resolved] == [
            "session-policy",
            "workspace-policy",
            "scope-policy",
        ]

    def test_inherited_resolution_prefers_higher_priority_over_specificity(self):
        policy_service, assignment_service = _build()
        _register_policy(policy_service, "session-policy")
        _register_policy(policy_service, "workspace-policy")

        assignment_service.assign("session-policy", "session", "scope-1", priority=1)
        assignment_service.assign("workspace-policy", "workspace", "scope-1", priority=10)

        resolved = assignment_service.resolve("scope-1")

        assert [policy.policy_id for policy in resolved] == ["workspace-policy", "session-policy"]

    def test_resolve_keeps_best_assignment_when_policy_assigned_at_multiple_levels(self):
        policy_service, assignment_service = _build()
        _register_policy(policy_service, "shared-policy")

        assignment_service.assign("shared-policy", "workspace", "scope-1", priority=1)
        assignment_service.assign("shared-policy", "session", "scope-1", priority=1)

        resolved = assignment_service.resolve("scope-1")

        assert [policy.policy_id for policy in resolved] == ["shared-policy"]

    def test_policies_rejects_unknown_scope_type(self):
        _policy_service, assignment_service = _build()

        with pytest.raises(Error):
            assignment_service.policies("unknown-scope-type", "scope-1")
