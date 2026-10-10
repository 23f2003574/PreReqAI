import pytest

from backend.session import (
    ExecutionSecretOperation as Operation,
    ExecutionSecretTrustError as Error,
    ExecutionSecretTrustLevel as TrustLevel,
    ExecutionSecretTrustPolicy,
    ExecutionSecretTrustService,
)


def _policy(policy_id, principal, trust_level, allowed_operations=frozenset(), enabled=True):
    return ExecutionSecretTrustPolicy(
        policy_id=policy_id,
        principal=principal,
        trust_level=trust_level,
        allowed_operations=allowed_operations,
        enabled=enabled,
    )


class TestExecutionSecretTrustService:
    def test_register_policy(self):
        trust_service = ExecutionSecretTrustService()

        registered = trust_service.register(_policy("policy-1", "component-a", TrustLevel.STANDARD))

        assert isinstance(registered, ExecutionSecretTrustPolicy)
        assert trust_service.policies("component-a") == [registered]

    def test_rejects_duplicate_policy_id(self):
        trust_service = ExecutionSecretTrustService()
        trust_service.register(_policy("policy-1", "component-a", TrustLevel.STANDARD))

        with pytest.raises(Error):
            trust_service.register(_policy("policy-1", "component-b", TrustLevel.LOW))

    def test_trust_lookup(self):
        trust_service = ExecutionSecretTrustService()
        trust_service.register(_policy("policy-1", "component-a", TrustLevel.STANDARD))

        assert trust_service.trust("component-a") == TrustLevel.STANDARD

    def test_trust_lookup_uses_highest_enabled_policy(self):
        trust_service = ExecutionSecretTrustService()
        trust_service.register(_policy("policy-1", "component-a", TrustLevel.LOW))
        trust_service.register(_policy("policy-2", "component-a", TrustLevel.HIGH))

        assert trust_service.trust("component-a") == TrustLevel.HIGH

    def test_inherited_permissions(self):
        trust_service = ExecutionSecretTrustService()
        trust_service.register(_policy("policy-1", "component-a", TrustLevel.HIGH))

        # HIGH trust inherits READ and ROTATE without either being
        # explicitly listed in allowed_operations.
        assert trust_service.authorize("component-a", Operation.READ) is True
        assert trust_service.authorize("component-a", Operation.ROTATE) is True

        # DELETE is the riskiest operation and is never inherited.
        assert trust_service.authorize("component-a", Operation.DELETE) is False

    def test_standard_trust_inherits_only_read(self):
        trust_service = ExecutionSecretTrustService()
        trust_service.register(_policy("policy-1", "component-a", TrustLevel.STANDARD))

        assert trust_service.authorize("component-a", Operation.READ) is True
        assert trust_service.authorize("component-a", Operation.ROTATE) is False

    def test_explicit_grant_extends_beyond_inheritance(self):
        trust_service = ExecutionSecretTrustService()
        trust_service.register(
            _policy("policy-1", "component-a", TrustLevel.HIGH, allowed_operations={Operation.DELETE})
        )

        assert trust_service.authorize("component-a", Operation.DELETE) is True

    def test_disabled_policy(self):
        trust_service = ExecutionSecretTrustService()
        trust_service.register(
            _policy("policy-1", "component-a", TrustLevel.HIGH, allowed_operations={Operation.DELETE})
        )

        disabled = trust_service.disable("policy-1")

        assert disabled.enabled is False
        assert trust_service.trust("component-a") == TrustLevel.LOW
        assert trust_service.authorize("component-a", Operation.READ) is False
        assert trust_service.authorize("component-a", Operation.DELETE) is False

    def test_disable_rejects_unknown_policy(self):
        trust_service = ExecutionSecretTrustService()

        with pytest.raises(Error):
            trust_service.disable("unknown-policy")

    def test_unknown_principal_defaults_to_low(self):
        trust_service = ExecutionSecretTrustService()

        assert trust_service.trust("component-a") == TrustLevel.LOW
        assert trust_service.policies("component-a") == []

    def test_operation_rejection(self):
        trust_service = ExecutionSecretTrustService()
        trust_service.register(_policy("policy-1", "component-a", TrustLevel.LOW))

        assert trust_service.authorize("component-a", Operation.READ) is False
        assert trust_service.authorize("component-a", Operation.ROTATE) is False
        assert trust_service.authorize("component-a", Operation.DELETE) is False

    def test_unknown_principal_operation_rejection(self):
        trust_service = ExecutionSecretTrustService()

        assert trust_service.authorize("component-a", Operation.READ) is False

    def test_rejects_invalid_arguments(self):
        trust_service = ExecutionSecretTrustService()

        with pytest.raises(Error):
            trust_service.trust("")

        with pytest.raises(Error):
            trust_service.authorize("", Operation.READ)

        with pytest.raises(Error):
            trust_service.authorize("component-a", "not-a-real-operation")

        with pytest.raises(Error):
            trust_service.disable("")

        with pytest.raises(Error):
            trust_service.policies("")
