import pytest

from backend.session import (
    ExecutionNetworkEndpointHealth,
    ExecutionNetworkEndpointHealthError as Error,
    ExecutionNetworkEndpointHealthService,
)


class _FakeEndpoint:
    def __init__(self, endpoint_id, status):
        self.endpoint_id = endpoint_id
        self.status = status


class _FakeEndpointService:
    def __init__(self):
        self._endpoints = {}

    def add(self, endpoint_id, status="ACTIVE"):
        self._endpoints[endpoint_id] = _FakeEndpoint(endpoint_id, status)

    def set_status(self, endpoint_id, status):
        self._endpoints[endpoint_id] = _FakeEndpoint(endpoint_id, status)

    def get(self, endpoint_id):
        if endpoint_id not in self._endpoints:
            raise ValueError(f"unknown endpoint {endpoint_id!r}")

        return self._endpoints[endpoint_id]


class _FakeProber:
    def __init__(self):
        self._latency_by_endpoint = {}
        self._failure_by_endpoint = {}
        self.measured = []

    def set_latency(self, endpoint_id, latency_ms):
        self._failure_by_endpoint.pop(endpoint_id, None)
        self._latency_by_endpoint[endpoint_id] = latency_ms

    def set_failure(self, endpoint_id, message):
        self._latency_by_endpoint.pop(endpoint_id, None)
        self._failure_by_endpoint[endpoint_id] = message

    def measure(self, endpoint):
        self.measured.append(endpoint.endpoint_id)

        if endpoint.endpoint_id in self._failure_by_endpoint:
            raise ConnectionError(self._failure_by_endpoint[endpoint.endpoint_id])

        return self._latency_by_endpoint[endpoint.endpoint_id]


def _build(degraded_latency_ms=200.0):
    endpoint_service = _FakeEndpointService()
    prober = _FakeProber()
    service = ExecutionNetworkEndpointHealthService(
        endpoint_service, prober, degraded_latency_ms=degraded_latency_ms
    )

    return endpoint_service, prober, service


class TestExecutionNetworkEndpointHealthService:
    def test_healthy_endpoint(self):
        endpoint_service, prober, service = _build()
        endpoint_service.add("endpoint-1")
        prober.set_latency("endpoint-1", 50)

        snapshot = service.check("endpoint-1")

        assert isinstance(snapshot, ExecutionNetworkEndpointHealth)
        assert snapshot.status == "HEALTHY"
        assert snapshot.latency_ms == 50
        assert snapshot.failure_reason is None
        assert service.healthy("endpoint-1") is True

    def test_degraded_latency(self):
        endpoint_service, prober, service = _build()
        endpoint_service.add("endpoint-1")
        prober.set_latency("endpoint-1", 350)

        snapshot = service.check("endpoint-1")

        assert snapshot.status == "DEGRADED"
        assert snapshot.latency_ms == 350
        assert snapshot.failure_reason is not None
        assert service.healthy("endpoint-1") is False

    def test_unreachable_endpoint(self):
        endpoint_service, prober, service = _build()
        endpoint_service.add("endpoint-1")
        prober.set_failure("endpoint-1", "connection refused")

        snapshot = service.check("endpoint-1")

        assert snapshot.status == "UNREACHABLE"
        assert snapshot.latency_ms is None
        assert snapshot.failure_reason == "connection refused"
        assert service.healthy("endpoint-1") is False

    def test_inactive_endpoint_is_rejected(self):
        endpoint_service, prober, service = _build()
        endpoint_service.add("endpoint-1", status="REMOVED")
        prober.set_latency("endpoint-1", 50)

        with pytest.raises(Error):
            service.check("endpoint-1")

        assert prober.measured == []

    def test_history_ordering(self):
        endpoint_service, prober, service = _build()
        endpoint_service.add("endpoint-1")

        prober.set_latency("endpoint-1", 50)
        first = service.check("endpoint-1")

        prober.set_latency("endpoint-1", 350)
        second = service.check("endpoint-1")

        prober.set_failure("endpoint-1", "timed out")
        third = service.check("endpoint-1")

        history = service.history("endpoint-1")

        assert [snapshot.status for snapshot in history] == ["HEALTHY", "DEGRADED", "UNREACHABLE"]
        assert history == (first, second, third)

    def test_failure_reason_recorded_per_status(self):
        endpoint_service, prober, service = _build()
        endpoint_service.add("endpoint-1")

        prober.set_latency("endpoint-1", 50)
        healthy = service.check("endpoint-1")
        assert healthy.failure_reason is None

        prober.set_latency("endpoint-1", 500)
        degraded = service.check("endpoint-1")
        assert "500" in degraded.failure_reason

        prober.set_failure("endpoint-1", "no route to host")
        unreachable = service.check("endpoint-1")
        assert unreachable.failure_reason == "no route to host"

    def test_check_does_not_mutate_endpoint_configuration(self):
        endpoint_service, prober, service = _build()
        endpoint_service.add("endpoint-1")
        prober.set_latency("endpoint-1", 50)

        service.check("endpoint-1")

        endpoint = endpoint_service.get("endpoint-1")
        assert endpoint.status == "ACTIVE"

    def test_history_for_unchecked_endpoint_is_rejected(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.history("does-not-exist")

    def test_check_unknown_endpoint_is_rejected(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.check("does-not-exist")

    def test_unhealthy_sweep(self):
        endpoint_service, prober, service = _build()
        endpoint_service.add("endpoint-1")
        endpoint_service.add("endpoint-2")
        prober.set_latency("endpoint-1", 50)
        prober.set_failure("endpoint-2", "connection refused")
        service.check("endpoint-1")
        service.check("endpoint-2")

        unhealthy = service.unhealthy()

        assert len(unhealthy) == 1
        assert unhealthy[0].endpoint_id == "endpoint-2"
        assert unhealthy[0].status == "UNREACHABLE"
