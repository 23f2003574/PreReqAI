import pytest

from backend.session import (
    ExecutionPolicy,
    ExecutionPolicyError as Error,
    ExecutionPolicyService,
)


def _policy(policy_id="policy-1", name="default-policy", rules=("read", "write"), enabled=True):
    return ExecutionPolicy(
        policy_id=policy_id,
        name=name,
        rules=frozenset(rules),
        enabled=enabled,
    )


class TestExecutionPolicyService:
    def test_register_and_get(self):
        service = ExecutionPolicyService()
        policy = _policy()

        registered = service.register(policy)

        assert registered is policy
        assert service.get("policy-1") is policy

    def test_get_unknown_policy_is_an_error(self):
        service = ExecutionPolicyService()

        with pytest.raises(Error):
            service.get("unknown-policy")

    def test_duplicate_policy_id_is_rejected(self):
        service = ExecutionPolicyService()
        service.register(_policy())

        with pytest.raises(Error):
            service.register(_policy())

    def test_update_rules(self):
        service = ExecutionPolicyService()
        service.register(_policy())

        updated = service.update("policy-1", frozenset({"read"}))

        assert updated.rules == frozenset({"read"})
        assert service.get("policy-1") == updated

    def test_update_rejects_empty_rules(self):
        service = ExecutionPolicyService()
        service.register(_policy())

        with pytest.raises(Error):
            service.update("policy-1", frozenset())

    def test_update_unknown_policy_is_an_error(self):
        service = ExecutionPolicyService()

        with pytest.raises(Error):
            service.update("unknown-policy", frozenset({"read"}))

    def test_empty_rules_rejected_on_construction(self):
        with pytest.raises(Error):
            _policy(rules=())

    def test_disable(self):
        service = ExecutionPolicyService()
        service.register(_policy())

        disabled = service.disable("policy-1")

        assert disabled.enabled is False
        assert service.get("policy-1").enabled is False

    def test_disable_unknown_policy_is_an_error(self):
        service = ExecutionPolicyService()

        with pytest.raises(Error):
            service.disable("unknown-policy")

    def test_list(self):
        service = ExecutionPolicyService()
        first = service.register(_policy("policy-1"))
        second = service.register(_policy("policy-2"))

        assert service.list() == [first, second]

    def test_history_preservation(self):
        service = ExecutionPolicyService()
        registered = service.register(_policy())

        updated = service.update("policy-1", frozenset({"read"}))
        disabled = service.disable("policy-1")

        assert service.history("policy-1") == [registered, updated, disabled]

    def test_history_unknown_policy_is_an_error(self):
        service = ExecutionPolicyService()

        with pytest.raises(Error):
            service.history("unknown-policy")

    def test_register_rejects_non_policy(self):
        service = ExecutionPolicyService()

        with pytest.raises(Error):
            service.register("not-a-policy")
