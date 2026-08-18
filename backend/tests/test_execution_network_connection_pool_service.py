import pytest

from backend.session import (
    ExecutionNetworkConnectionPool,
    ExecutionNetworkConnectionPoolError as Error,
    ExecutionNetworkConnectionPoolService,
)


class _FakeHealthService:
    def __init__(self):
        self._healthy = {}

    def set_healthy(self, endpoint_id, value):
        self._healthy[endpoint_id] = value

    def healthy(self, endpoint_id):
        if endpoint_id not in self._healthy:
            raise ValueError(f"unknown endpoint {endpoint_id!r}")

        return self._healthy[endpoint_id]


def _build():
    health_service = _FakeHealthService()
    service = ExecutionNetworkConnectionPoolService(health_service)

    return health_service, service


class TestExecutionNetworkConnectionPoolService:
    def test_configure_acquire_release(self):
        health_service, service = _build()
        health_service.set_healthy("endpoint-1", True)
        pool = service.configure("runtime-1", "endpoint-1", 2)

        assert isinstance(pool, ExecutionNetworkConnectionPool)
        assert pool.idle_connections == ()

        connection_id = service.acquire("runtime-1", "endpoint-1")
        assert isinstance(connection_id, str) and connection_id

        stats = service.stats("runtime-1", "endpoint-1")
        assert stats == {"idle": 0, "checked_out": 1, "max_idle": 2}

        released = service.release(connection_id)
        assert released.idle_connections == (connection_id,)

        stats = service.stats("runtime-1", "endpoint-1")
        assert stats == {"idle": 1, "checked_out": 0, "max_idle": 2}

    def test_connection_reuse(self):
        health_service, service = _build()
        health_service.set_healthy("endpoint-1", True)
        service.configure("runtime-1", "endpoint-1", 2)

        first = service.acquire("runtime-1", "endpoint-1")
        service.release(first)

        second = service.acquire("runtime-1", "endpoint-1")

        assert second == first
        assert service.stats("runtime-1", "endpoint-1")["idle"] == 0

    def test_idle_cap_enforcement(self):
        health_service, service = _build()
        health_service.set_healthy("endpoint-1", True)
        service.configure("runtime-1", "endpoint-1", 1)

        first = service.acquire("runtime-1", "endpoint-1")
        second = service.acquire("runtime-1", "endpoint-1")

        service.release(first)
        released = service.release(second)

        assert len(released.idle_connections) == 1
        assert service.stats("runtime-1", "endpoint-1")["idle"] == 1

    def test_unhealthy_eviction(self):
        health_service, service = _build()
        health_service.set_healthy("endpoint-1", True)
        service.configure("runtime-1", "endpoint-1", 2)
        first = service.acquire("runtime-1", "endpoint-1")
        service.release(first)

        health_service.set_healthy("endpoint-1", False)
        second = service.acquire("runtime-1", "endpoint-1")

        assert second != first
        assert service.stats("runtime-1", "endpoint-1")["idle"] == 0

    def test_pool_isolation(self):
        health_service, service = _build()
        health_service.set_healthy("endpoint-1", True)
        health_service.set_healthy("endpoint-2", True)
        service.configure("runtime-1", "endpoint-1", 2)
        service.configure("runtime-1", "endpoint-2", 2)

        connection_a = service.acquire("runtime-1", "endpoint-1")
        service.release(connection_a)
        connection_b = service.acquire("runtime-1", "endpoint-2")
        service.release(connection_b)

        assert service.stats("runtime-1", "endpoint-1")["idle"] == 1
        assert service.stats("runtime-1", "endpoint-2")["idle"] == 1
        assert connection_a != connection_b

    def test_evict_clears_idle_but_not_checked_out(self):
        health_service, service = _build()
        health_service.set_healthy("endpoint-1", True)
        service.configure("runtime-1", "endpoint-1", 2)
        idle_connection = service.acquire("runtime-1", "endpoint-1")
        service.release(idle_connection)
        checked_out = service.acquire("runtime-1", "endpoint-1")

        evicted = service.evict("runtime-1", "endpoint-1")

        assert evicted.idle_connections == ()
        assert service.stats("runtime-1", "endpoint-1") == {"idle": 0, "checked_out": 1, "max_idle": 2}

        service.release(checked_out)

    def test_max_idle_must_be_at_least_one(self):
        _, service = _build()

        with pytest.raises(Error):
            service.configure("runtime-1", "endpoint-1", 0)

    def test_release_unknown_connection_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.release("does-not-exist")

    def test_operations_without_configured_pool_are_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.acquire("runtime-1", "endpoint-1")

        with pytest.raises(Error):
            service.evict("runtime-1", "endpoint-1")

        with pytest.raises(Error):
            service.stats("runtime-1", "endpoint-1")

    def test_reconfigure_discards_prior_pool_state(self):
        health_service, service = _build()
        health_service.set_healthy("endpoint-1", True)
        service.configure("runtime-1", "endpoint-1", 2)
        connection_id = service.acquire("runtime-1", "endpoint-1")
        service.release(connection_id)

        service.configure("runtime-1", "endpoint-1", 2)

        assert service.stats("runtime-1", "endpoint-1") == {"idle": 0, "checked_out": 0, "max_idle": 2}

        with pytest.raises(Error):
            service.release(connection_id)
