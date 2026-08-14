from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionPolicy,
    ExecutionPolicyError,
    ExecutionPolicyException,
    ExecutionPolicyExceptionError as Error,
    ExecutionPolicyExceptionService,
    ExecutionPolicyService,
)


def _build():
    policy_service = ExecutionPolicyService()
    exception_service = ExecutionPolicyExceptionService(policy_service)
    return policy_service, exception_service


def _register(policy_service, policy_id="policy-1"):
    return policy_service.register(
        ExecutionPolicy(
            policy_id=policy_id,
            name=policy_id,
            rules=frozenset({"read"}),
        )
    )


def _future():
    return datetime.now(timezone.utc) + timedelta(hours=1)


def _past():
    return datetime.now(timezone.utc) - timedelta(seconds=1)


class TestExecutionPolicyExceptionService:
    def test_create_and_validate(self):
        policy_service, exception_service = _build()
        _register(policy_service)

        exception = exception_service.create("policy-1", "scope-1", "delete", "one-off approval", _future())

        assert isinstance(exception, ExecutionPolicyException)
        assert exception.reason == "one-off approval"
        assert exception_service.validate(exception.exception_id) is True

    def test_validate_unknown_exception_is_an_error(self):
        _policy_service, exception_service = _build()

        with pytest.raises(Error):
            exception_service.validate("unknown-exception")

    def test_active_lookup(self):
        policy_service, exception_service = _build()
        _register(policy_service)

        exception = exception_service.create("policy-1", "scope-1", "delete", "reason", _future())

        assert exception_service.active("scope-1") == [exception]
        assert exception_service.active("scope-2") == []

    def test_expiry(self):
        policy_service, exception_service = _build()
        _register(policy_service)

        exception = exception_service.create("policy-1", "scope-1", "delete", "reason", _past())

        assert exception_service.validate(exception.exception_id) is False
        assert exception_service.active("scope-1") == []
        assert exception_service.expired() == [exception]

    def test_revoke(self):
        policy_service, exception_service = _build()
        _register(policy_service)

        exception = exception_service.create("policy-1", "scope-1", "delete", "reason", _future())

        revoked = exception_service.revoke(exception.exception_id)

        assert revoked == exception
        assert exception_service.validate(exception.exception_id) is False
        assert exception_service.active("scope-1") == []

    def test_revoke_unknown_exception_is_an_error(self):
        _policy_service, exception_service = _build()

        with pytest.raises(Error):
            exception_service.revoke("unknown-exception")

    def test_missing_policy(self):
        _policy_service, exception_service = _build()

        with pytest.raises(ExecutionPolicyError):
            exception_service.create("unknown-policy", "scope-1", "delete", "reason", _future())

    def test_missing_expiry(self):
        policy_service, exception_service = _build()
        _register(policy_service)

        with pytest.raises(Error):
            exception_service.create("policy-1", "scope-1", "delete", "reason", None)

    def test_reason_is_retained_after_expiry_and_revocation(self):
        policy_service, exception_service = _build()
        _register(policy_service)

        exception_service.create("policy-1", "scope-1", "delete", "temporary access", _past())
        revoked = exception_service.create("policy-1", "scope-1", "delete", "temporary access", _future())
        revoked_record = exception_service.revoke(revoked.exception_id)

        assert exception_service.expired()[0].reason == "temporary access"
        assert revoked_record.reason == "temporary access"
