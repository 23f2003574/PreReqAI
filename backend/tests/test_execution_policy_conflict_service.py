import pytest

from backend.session import (
    ExecutionPolicy,
    ExecutionPolicyConflict,
    ExecutionPolicyConflictError as Error,
    ExecutionPolicyConflictService,
    ExecutionPolicyService,
)


def _build():
    policy_service = ExecutionPolicyService()
    conflict_service = ExecutionPolicyConflictService(policy_service)
    return policy_service, conflict_service


def _register(policy_service, policy_id, rules):
    return policy_service.register(
        ExecutionPolicy(
            policy_id=policy_id,
            name=policy_id,
            rules=frozenset(rules),
        )
    )


class TestExecutionPolicyConflictService:
    def test_detect_conflict(self):
        policy_service, conflict_service = _build()
        _register(policy_service, "policy-a", {"delete"})
        _register(policy_service, "policy-b", {"!delete"})

        conflicts = conflict_service.detect(["policy-a", "policy-b"])

        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert isinstance(conflict, ExecutionPolicyConflict)
        assert conflict.rule == "delete"
        assert set(conflict.policy_ids) == {"policy-a", "policy-b"}
        assert conflict.status == "unresolved"
        assert conflict.resolution is None

    def test_no_conflict_case(self):
        policy_service, conflict_service = _build()
        _register(policy_service, "policy-a", {"read"})
        _register(policy_service, "policy-b", {"write"})

        assert conflict_service.detect(["policy-a", "policy-b"]) == []

    def test_multiple_conflicts(self):
        policy_service, conflict_service = _build()
        _register(policy_service, "policy-a", {"delete", "admin"})
        _register(policy_service, "policy-b", {"!delete", "!admin"})

        conflicts = conflict_service.detect(["policy-a", "policy-b"])

        assert sorted(conflict.rule for conflict in conflicts) == ["admin", "delete"]

    def test_resolve_conflict(self):
        policy_service, conflict_service = _build()
        _register(policy_service, "policy-a", {"delete"})
        _register(policy_service, "policy-b", {"!delete"})

        conflict = conflict_service.detect(["policy-a", "policy-b"])[0]

        resolved = conflict_service.resolve(conflict.conflict_id, "policy-a wins")

        assert resolved.status == "resolved"
        assert resolved.resolution == "policy-a wins"

    def test_resolve_requires_explicit_resolution(self):
        policy_service, conflict_service = _build()
        _register(policy_service, "policy-a", {"delete"})
        _register(policy_service, "policy-b", {"!delete"})

        conflict = conflict_service.detect(["policy-a", "policy-b"])[0]

        with pytest.raises(Error):
            conflict_service.resolve(conflict.conflict_id, "")

    def test_resolve_unknown_conflict_is_an_error(self):
        _policy_service, conflict_service = _build()

        with pytest.raises(Error):
            conflict_service.resolve("unknown-conflict", "some resolution")

    def test_unresolved_blocking(self):
        policy_service, conflict_service = _build()
        _register(policy_service, "policy-a", {"delete", "admin"})
        _register(policy_service, "policy-b", {"!delete", "!admin"})

        conflicts = conflict_service.detect(["policy-a", "policy-b"], scope_id="scope-1")

        assert len(conflict_service.unresolved("scope-1")) == 2

        conflict_service.resolve(conflicts[0].conflict_id, "resolved manually")

        remaining = conflict_service.unresolved("scope-1")
        assert len(remaining) == 1
        assert remaining[0].conflict_id == conflicts[1].conflict_id

        conflict_service.resolve(conflicts[1].conflict_id, "resolved manually")

        assert conflict_service.unresolved("scope-1") == []

    def test_clear_forgets_scope_tracking_but_preserves_history(self):
        policy_service, conflict_service = _build()
        _register(policy_service, "policy-a", {"delete"})
        _register(policy_service, "policy-b", {"!delete"})

        conflicts = conflict_service.detect(["policy-a", "policy-b"], scope_id="scope-1")
        cleared = conflict_service.clear("scope-1")

        assert cleared == conflicts
        assert conflict_service.unresolved("scope-1") == []
        assert conflict_service.history(conflicts[0].conflict_id) == [conflicts[0]]

    def test_history_preservation(self):
        policy_service, conflict_service = _build()
        _register(policy_service, "policy-a", {"delete"})
        _register(policy_service, "policy-b", {"!delete"})

        detected = conflict_service.detect(["policy-a", "policy-b"])[0]
        resolved = conflict_service.resolve(detected.conflict_id, "policy-a wins")

        assert conflict_service.history(detected.conflict_id) == [detected, resolved]

    def test_history_unknown_conflict_is_an_error(self):
        _policy_service, conflict_service = _build()

        with pytest.raises(Error):
            conflict_service.history("unknown-conflict")
