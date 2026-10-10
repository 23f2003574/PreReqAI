import pytest

from backend.session import (
    ExecutionSecretAccessError as Error,
    ExecutionSecretAccessService,
    ExecutionSecretOperation as Operation,
    ExecutionSecretPolicy,
)


class TestExecutionSecretAccessService:
    def test_grant_and_authorize(self):
        access_service = ExecutionSecretAccessService()

        granted = access_service.grant("secret-1", "component-a", {Operation.READ})

        assert isinstance(granted, ExecutionSecretPolicy)
        assert access_service.authorize("secret-1", "component-a", Operation.READ) is True

    def test_default_denial(self):
        access_service = ExecutionSecretAccessService()

        assert access_service.authorize("secret-1", "component-a", Operation.READ) is False

        access_service.grant("secret-1", "component-a", {Operation.READ})

        # A principal with no grant of its own is still denied.
        assert access_service.authorize("secret-1", "component-b", Operation.READ) is False

    def test_operation_isolation(self):
        access_service = ExecutionSecretAccessService()

        access_service.grant("secret-1", "component-a", {Operation.READ})

        assert access_service.authorize("secret-1", "component-a", Operation.READ) is True
        assert access_service.authorize("secret-1", "component-a", Operation.ROTATE) is False
        assert access_service.authorize("secret-1", "component-a", Operation.DELETE) is False

    def test_revoke(self):
        access_service = ExecutionSecretAccessService()

        granted = access_service.grant("secret-1", "component-a", {Operation.READ})

        revoked = access_service.revoke(granted.policy_id)

        assert revoked == granted
        assert access_service.authorize("secret-1", "component-a", Operation.READ) is False

        with pytest.raises(Error):
            access_service.revoke(granted.policy_id)

    def test_disabled_policy_denies_access(self):
        access_service = ExecutionSecretAccessService()

        access_service.grant("secret-1", "component-a", {Operation.READ}, enabled=False)

        assert access_service.authorize("secret-1", "component-a", Operation.READ) is False

    def test_policy_lookup(self):
        access_service = ExecutionSecretAccessService()

        first = access_service.grant("secret-1", "component-a", {Operation.READ})
        second = access_service.grant("secret-1", "component-b", {Operation.ROTATE})
        access_service.grant("secret-2", "component-a", {Operation.DELETE})

        listed = access_service.policies("secret-1")

        assert listed == [first, second]

    def test_multiple_grants_are_additive(self):
        access_service = ExecutionSecretAccessService()

        access_service.grant("secret-1", "component-a", {Operation.READ})
        access_service.grant("secret-1", "component-a", {Operation.ROTATE})

        assert access_service.authorize("secret-1", "component-a", Operation.READ) is True
        assert access_service.authorize("secret-1", "component-a", Operation.ROTATE) is True

    def test_rejects_invalid_arguments(self):
        access_service = ExecutionSecretAccessService()

        with pytest.raises(Error):
            access_service.grant("", "component-a", {Operation.READ})

        with pytest.raises(Error):
            access_service.grant("secret-1", "", {Operation.READ})

        with pytest.raises(Error):
            access_service.grant("secret-1", "component-a", set())

        with pytest.raises(Error):
            access_service.grant("secret-1", "component-a", {"not-a-real-operation"})

        with pytest.raises(Error):
            access_service.authorize("secret-1", "component-a", "not-a-real-operation")

        with pytest.raises(Error):
            access_service.revoke("")

        with pytest.raises(Error):
            access_service.policies("")
