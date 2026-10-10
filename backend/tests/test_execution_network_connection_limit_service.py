import pytest

from backend.session import (
    ExecutionNetworkConnectionLimit,
    ExecutionNetworkConnectionLimitError as Error,
    ExecutionNetworkConnectionLimitService,
)


class TestExecutionNetworkConnectionLimitService:
    def test_configure_limit(self):
        service = ExecutionNetworkConnectionLimitService()

        limit = service.configure("runtime-1", 2)

        assert isinstance(limit, ExecutionNetworkConnectionLimit)
        assert limit.runtime_id == "runtime-1"
        assert limit.max_connections == 2
        assert limit.enabled is True

    def test_max_connections_must_be_at_least_one(self):
        service = ExecutionNetworkConnectionLimitService()

        with pytest.raises(Error):
            service.configure("runtime-1", 0)

        with pytest.raises(Error):
            service.configure("runtime-1", -1)

    def test_acquire_and_release(self):
        service = ExecutionNetworkConnectionLimitService()
        service.configure("runtime-1", 2)

        service.acquire("runtime-1", "connection-1")

        assert service.active("runtime-1") == ("connection-1",)
        assert service.can_open("runtime-1") is True

        service.release("runtime-1", "connection-1")

        assert service.active("runtime-1") == ()
        assert service.can_open("runtime-1") is True

    def test_capacity_exhaustion(self):
        service = ExecutionNetworkConnectionLimitService()
        service.configure("runtime-1", 1)
        service.acquire("runtime-1", "connection-1")

        assert service.can_open("runtime-1") is False

        with pytest.raises(Error):
            service.acquire("runtime-1", "connection-2")

    def test_release_immediately_frees_capacity(self):
        service = ExecutionNetworkConnectionLimitService()
        service.configure("runtime-1", 1)
        service.acquire("runtime-1", "connection-1")
        service.release("runtime-1", "connection-1")

        service.acquire("runtime-1", "connection-2")

        assert service.active("runtime-1") == ("connection-2",)

    def test_duplicate_acquire_rejection(self):
        service = ExecutionNetworkConnectionLimitService()
        service.configure("runtime-1", 2)
        service.acquire("runtime-1", "connection-1")

        with pytest.raises(Error):
            service.acquire("runtime-1", "connection-1")

    def test_connection_isolation(self):
        service = ExecutionNetworkConnectionLimitService()
        service.configure("runtime-1", 1)
        service.configure("runtime-2", 1)

        service.acquire("runtime-1", "connection-1")
        service.acquire("runtime-2", "connection-1")

        assert service.active("runtime-1") == ("connection-1",)
        assert service.active("runtime-2") == ("connection-1",)
        assert service.can_open("runtime-1") is False
        assert service.can_open("runtime-2") is False

    def test_disabled_limit(self):
        service = ExecutionNetworkConnectionLimitService()
        service.configure("runtime-1", 1, enabled=False)
        service.acquire("runtime-1", "connection-1")

        assert service.can_open("runtime-1") is True

        service.acquire("runtime-1", "connection-2")

        assert set(service.active("runtime-1")) == {"connection-1", "connection-2"}

    def test_release_is_idempotent(self):
        service = ExecutionNetworkConnectionLimitService()
        service.configure("runtime-1", 1)

        service.release("runtime-1", "does-not-exist")

        assert service.active("runtime-1") == ()

    def test_reconfigure_clears_prior_connections(self):
        service = ExecutionNetworkConnectionLimitService()
        service.configure("runtime-1", 2)
        service.acquire("runtime-1", "connection-1")

        service.configure("runtime-1", 2)

        assert service.active("runtime-1") == ()

    def test_operations_without_configured_limit_are_rejected(self):
        service = ExecutionNetworkConnectionLimitService()

        with pytest.raises(Error):
            service.can_open("runtime-1")

        with pytest.raises(Error):
            service.acquire("runtime-1", "connection-1")

        with pytest.raises(Error):
            service.release("runtime-1", "connection-1")

        with pytest.raises(Error):
            service.active("runtime-1")
