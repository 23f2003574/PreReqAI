import pytest

from backend.session import (
    ExecutionSecretAccessService,
    ExecutionSecretLeaseService,
    ExecutionSecretOperation as Operation,
    ExecutionSecretRevocation,
    ExecutionSecretRevocationError as Error,
    ExecutionSecretRevocationService,
)


def _build():
    access_service = ExecutionSecretAccessService()
    lease_service = ExecutionSecretLeaseService(access_service)
    revocation_service = ExecutionSecretRevocationService(lease_service)
    return access_service, lease_service, revocation_service


class TestExecutionSecretRevocationService:
    def test_revoke_secret(self):
        _access_service, _lease_service, revocation_service = _build()

        revocation = revocation_service.revoke("secret-1", "compromised credential")

        assert isinstance(revocation, ExecutionSecretRevocation)
        assert revocation.secret_id == "secret-1"
        assert revocation.reason == "compromised credential"

    def test_access_blocked_after_revoke(self):
        _access_service, _lease_service, revocation_service = _build()

        assert revocation_service.is_revoked("secret-1") is False

        revocation_service.revoke("secret-1", "compromised credential")

        assert revocation_service.is_revoked("secret-1") is True

    def test_active_lease_invalidation(self):
        access_service, lease_service, revocation_service = _build()
        access_service.grant("secret-1", "component-a", {Operation.READ})
        access_service.grant("secret-1", "component-b", {Operation.READ})

        lease_a = lease_service.acquire("secret-1", "component-a")
        lease_b = lease_service.acquire("secret-1", "component-b")

        revocation_service.revoke("secret-1", "compromised credential")

        assert lease_service.active("secret-1") == []

        with pytest.raises(Exception):
            lease_service.renew(lease_a.lease_id)

        with pytest.raises(Exception):
            lease_service.renew(lease_b.lease_id)

    def test_restore(self):
        _access_service, _lease_service, revocation_service = _build()
        revocation_service.revoke("secret-1", "compromised credential")

        restored = revocation_service.restore("secret-1", authorized_by="security-admin")

        assert restored is True
        assert revocation_service.is_revoked("secret-1") is False

        # A restored secret can be revoked again.
        revocation_service.revoke("secret-1", "second incident")

    def test_restore_requires_explicit_authorization(self):
        _access_service, _lease_service, revocation_service = _build()
        revocation_service.revoke("secret-1", "compromised credential")

        with pytest.raises(Error):
            revocation_service.restore("secret-1", authorized_by="")

        with pytest.raises(TypeError):
            revocation_service.restore("secret-1")

    def test_restore_requires_currently_revoked(self):
        _access_service, _lease_service, revocation_service = _build()

        with pytest.raises(Error):
            revocation_service.restore("secret-1", authorized_by="security-admin")

    def test_revocation_history(self):
        _access_service, _lease_service, revocation_service = _build()

        first = revocation_service.revoke("secret-1", "compromised credential")
        revocation_service.restore("secret-1", authorized_by="security-admin")
        second = revocation_service.revoke("secret-1", "second incident")

        assert revocation_service.history("secret-1") == [first, second]

    def test_history_is_isolated_per_secret(self):
        _access_service, _lease_service, revocation_service = _build()

        revocation_service.revoke("secret-1", "compromised credential")

        assert revocation_service.history("secret-2") == []

    def test_repeated_revoke_rejection(self):
        _access_service, _lease_service, revocation_service = _build()
        revocation_service.revoke("secret-1", "compromised credential")

        with pytest.raises(Error):
            revocation_service.revoke("secret-1", "compromised credential again")

    def test_rejects_invalid_arguments(self):
        _access_service, _lease_service, revocation_service = _build()

        with pytest.raises(Error):
            revocation_service.revoke("", "reason")

        with pytest.raises(Error):
            revocation_service.revoke("secret-1", "")

        with pytest.raises(Error):
            revocation_service.is_revoked("")

        with pytest.raises(Error):
            revocation_service.history("")
