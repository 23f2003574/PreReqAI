from datetime import (
    timedelta,
)

import pytest

from backend.session import (
    ExecutionSecretAccessService,
    ExecutionSecretLease,
    ExecutionSecretLeaseError as Error,
    ExecutionSecretLeaseService,
    ExecutionSecretOperation as Operation,
)


def _build(ttl=timedelta(minutes=15)):
    access_service = ExecutionSecretAccessService()
    lease_service = ExecutionSecretLeaseService(access_service, ttl=ttl)
    return access_service, lease_service


def _grant_read(access_service, secret_id="secret-1", principal="component-a"):
    access_service.grant(secret_id, principal, {Operation.READ})


class TestExecutionSecretLeaseService:
    def test_acquire_lease(self):
        access_service, lease_service = _build()
        _grant_read(access_service)

        lease = lease_service.acquire("secret-1", "component-a")

        assert isinstance(lease, ExecutionSecretLease)
        assert lease.secret_id == "secret-1"
        assert lease.principal == "component-a"
        assert lease.status == "ACTIVE"

    def test_renew_lease(self):
        access_service, lease_service = _build()
        _grant_read(access_service)
        lease = lease_service.acquire("secret-1", "component-a")

        renewed = lease_service.renew(lease.lease_id)

        assert renewed.lease_id == lease.lease_id
        assert renewed.status == "ACTIVE"
        assert renewed.expires_at > lease.expires_at

    def test_release_lease(self):
        access_service, lease_service = _build()
        _grant_read(access_service)
        lease = lease_service.acquire("secret-1", "component-a")

        released = lease_service.release(lease.lease_id)

        assert released.status == "RELEASED"
        assert lease_service.active("secret-1") == []

        with pytest.raises(Error):
            lease_service.release(lease.lease_id)

        with pytest.raises(Error):
            lease_service.renew(lease.lease_id)

    def test_policy_denial(self):
        _access_service, lease_service = _build()

        with pytest.raises(Error):
            lease_service.acquire("secret-1", "component-a")

    def test_policy_denial_for_disabled_grant(self):
        access_service, lease_service = _build()
        access_service.grant("secret-1", "component-a", {Operation.READ}, enabled=False)

        with pytest.raises(Error):
            lease_service.acquire("secret-1", "component-a")

    def test_duplicate_lease_rejection(self):
        access_service, lease_service = _build()
        _grant_read(access_service)
        lease_service.acquire("secret-1", "component-a")

        with pytest.raises(Error):
            lease_service.acquire("secret-1", "component-a")

    def test_reacquire_after_release(self):
        access_service, lease_service = _build()
        _grant_read(access_service)
        first = lease_service.acquire("secret-1", "component-a")
        lease_service.release(first.lease_id)

        second = lease_service.acquire("secret-1", "component-a")

        assert second.lease_id != first.lease_id

    def test_expiry(self):
        access_service, lease_service = _build(ttl=timedelta(seconds=-1))
        _grant_read(access_service)

        lease = lease_service.acquire("secret-1", "component-a")

        assert lease_service.expired() == [lease]
        assert lease_service.active("secret-1") == []

        with pytest.raises(Error):
            lease_service.renew(lease.lease_id)

    def test_cleanup(self):
        access_service, lease_service = _build(ttl=timedelta(seconds=-1))
        _grant_read(access_service)
        lease = lease_service.acquire("secret-1", "component-a")

        updated = lease_service.cleanup()

        assert len(updated) == 1
        assert updated[0].lease_id == lease.lease_id
        assert updated[0].status == "EXPIRED"
        assert lease_service.expired() == []

        reacquired = lease_service.acquire("secret-1", "component-a")
        assert reacquired.lease_id != lease.lease_id

    def test_active_lookup(self):
        access_service, lease_service = _build()
        _grant_read(access_service, principal="component-a")
        _grant_read(access_service, principal="component-b")

        first = lease_service.acquire("secret-1", "component-a")
        second = lease_service.acquire("secret-1", "component-b")
        lease_service.release(first.lease_id)

        assert lease_service.active("secret-1") == [second]

    def test_rejects_unknown_lease(self):
        _access_service, lease_service = _build()

        with pytest.raises(Error):
            lease_service.renew("unknown-lease")

        with pytest.raises(Error):
            lease_service.release("unknown-lease")
