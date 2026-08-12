from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionSecret,
    ExecutionSecretError as Error,
    ExecutionSecretService,
)


def _secret(secret_id, session_id, name="api-key", value_ref="vault://api-key", expires_at=None):
    return ExecutionSecret(
        secret_id=secret_id,
        session_id=session_id,
        name=name,
        value_ref=value_ref,
        expires_at=expires_at,
    )


class TestExecutionSecretService:
    def test_register_and_get(self):
        secret_service = ExecutionSecretService()

        registered = secret_service.register("session-1", _secret("secret-1", "session-1"))

        assert isinstance(registered, ExecutionSecret)
        assert registered.value_ref == "vault://api-key"

        fetched = secret_service.get("session-1", "api-key")

        assert fetched == registered

    def test_get_is_a_miss_when_nothing_registered(self):
        secret_service = ExecutionSecretService()

        assert secret_service.get("session-1", "api-key") is None

    def test_session_isolation(self):
        secret_service = ExecutionSecretService()

        first = secret_service.register("session-1", _secret("secret-1", "session-1"))
        second = secret_service.register(
            "session-2", _secret("secret-2", "session-2", value_ref="vault://other-key")
        )

        assert secret_service.get("session-1", "api-key") == first
        assert secret_service.get("session-2", "api-key") == second
        assert secret_service.get("session-1", "api-key").value_ref != second.value_ref

    def test_rejects_duplicate_name_within_session(self):
        secret_service = ExecutionSecretService()

        secret_service.register("session-1", _secret("secret-1", "session-1"))

        with pytest.raises(Error):
            secret_service.register("session-1", _secret("secret-2", "session-1"))

        # Same name is fine again once scoped to a different session.
        secret_service.register("session-2", _secret("secret-3", "session-2"))

    def test_rejects_duplicate_secret_id(self):
        secret_service = ExecutionSecretService()

        secret_service.register("session-1", _secret("secret-1", "session-1", name="api-key"))

        with pytest.raises(Error):
            secret_service.register(
                "session-1", _secret("secret-1", "session-1", name="other-key")
            )

    def test_expiry(self):
        secret_service = ExecutionSecretService()
        expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        registered = secret_service.register(
            "session-1", _secret("secret-1", "session-1", expires_at=expired_at)
        )

        assert secret_service.get("session-1", "api-key") is None
        assert secret_service.expired() == [registered]

    def test_secret_without_expiry_never_expires(self):
        secret_service = ExecutionSecretService()

        secret_service.register("session-1", _secret("secret-1", "session-1"))

        assert secret_service.get("session-1", "api-key") is not None
        assert secret_service.expired() == []

    def test_removal_revokes_access_immediately(self):
        secret_service = ExecutionSecretService()

        registered = secret_service.register("session-1", _secret("secret-1", "session-1"))

        removed = secret_service.remove("secret-1")

        assert removed == registered
        assert secret_service.get("session-1", "api-key") is None

        with pytest.raises(Error):
            secret_service.remove("secret-1")

    def test_removal_frees_the_name_for_reuse(self):
        secret_service = ExecutionSecretService()

        secret_service.register("session-1", _secret("secret-1", "session-1"))
        secret_service.remove("secret-1")

        reregistered = secret_service.register("session-1", _secret("secret-2", "session-1"))

        assert secret_service.get("session-1", "api-key") == reregistered

    def test_cleanup_removes_only_expired_secrets(self):
        secret_service = ExecutionSecretService()
        expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        expired = secret_service.register(
            "session-1", _secret("secret-1", "session-1", expires_at=expired_at)
        )
        active = secret_service.register(
            "session-1", _secret("secret-2", "session-1", name="other-key")
        )

        removed = secret_service.cleanup()

        assert removed == [expired]
        assert secret_service.expired() == []
        assert secret_service.get("session-1", "other-key") == active

    def test_rejects_invalid_arguments(self):
        secret_service = ExecutionSecretService()

        with pytest.raises(Error):
            secret_service.register("", _secret("secret-1", ""))

        with pytest.raises(Error):
            secret_service.get("session-1", "")

        with pytest.raises(Error):
            secret_service.remove("")

    def test_rejects_secret_for_a_different_session(self):
        secret_service = ExecutionSecretService()

        with pytest.raises(Error):
            secret_service.register("session-1", _secret("secret-1", "session-2"))
