import pytest

from backend.session import (
    ExecutionNetworkRoute,
    ExecutionNetworkRouteError as Error,
    ExecutionNetworkRoutingService,
)


class _FakeEndpoint:
    def __init__(self, endpoint_id, runtime_id):
        self.endpoint_id = endpoint_id
        self.runtime_id = runtime_id


class _FakeEndpointService:
    def __init__(self):
        self._endpoints = {}

    def add(self, endpoint_id, runtime_id):
        self._endpoints[endpoint_id] = _FakeEndpoint(endpoint_id, runtime_id)

    def get(self, endpoint_id):
        if endpoint_id not in self._endpoints:
            raise ValueError(f"unknown endpoint {endpoint_id!r}")

        return self._endpoints[endpoint_id]


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
    endpoint_service = _FakeEndpointService()
    health_service = _FakeHealthService()
    service = ExecutionNetworkRoutingService(endpoint_service, health_service)

    return endpoint_service, health_service, service


class TestExecutionNetworkRoutingService:
    def test_route_registration(self):
        endpoint_service, _, service = _build()
        endpoint_service.add("endpoint-1", "runtime-1")

        route = service.register("runtime-1", "endpoint-1", 1)

        assert isinstance(route, ExecutionNetworkRoute)
        assert route.runtime_id == "runtime-1"
        assert route.endpoint_id == "endpoint-1"
        assert route.priority == 1
        assert route.status == "ACTIVE"

    def test_registration_rejects_mismatched_runtime(self):
        endpoint_service, _, service = _build()
        endpoint_service.add("endpoint-1", "runtime-2")

        with pytest.raises(Error):
            service.register("runtime-1", "endpoint-1", 1)

    def test_registration_rejects_unknown_endpoint(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.register("runtime-1", "does-not-exist", 1)

    def test_priority_resolution(self):
        endpoint_service, health_service, service = _build()
        endpoint_service.add("endpoint-a", "runtime-1")
        endpoint_service.add("endpoint-b", "runtime-1")
        health_service.set_healthy("endpoint-a", True)
        health_service.set_healthy("endpoint-b", True)
        service.register("runtime-1", "endpoint-a", 5)
        route_b = service.register("runtime-1", "endpoint-b", 1)

        resolved = service.resolve("runtime-1")

        assert resolved.route_id == route_b.route_id

    def test_unhealthy_endpoint_exclusion(self):
        endpoint_service, health_service, service = _build()
        endpoint_service.add("endpoint-a", "runtime-1")
        endpoint_service.add("endpoint-b", "runtime-1")
        health_service.set_healthy("endpoint-a", True)
        health_service.set_healthy("endpoint-b", False)
        route_a = service.register("runtime-1", "endpoint-a", 5)
        service.register("runtime-1", "endpoint-b", 1)

        resolved = service.resolve("runtime-1")

        assert resolved.route_id == route_a.route_id

    def test_rerouting(self):
        endpoint_service, health_service, service = _build()
        endpoint_service.add("endpoint-a", "runtime-1")
        endpoint_service.add("endpoint-b", "runtime-1")
        health_service.set_healthy("endpoint-a", True)
        health_service.set_healthy("endpoint-b", True)
        route_a = service.register("runtime-1", "endpoint-a", 2)
        route_b = service.register("runtime-1", "endpoint-b", 1)

        first = service.resolve("runtime-1")
        assert first.route_id == route_b.route_id

        health_service.set_healthy("endpoint-b", False)
        rerouted = service.reroute("runtime-1")

        assert rerouted.route_id == route_a.route_id

    def test_reroute_without_prior_resolve_is_rejected(self):
        endpoint_service, health_service, service = _build()
        endpoint_service.add("endpoint-a", "runtime-1")
        health_service.set_healthy("endpoint-a", True)
        service.register("runtime-1", "endpoint-a", 1)

        with pytest.raises(Error):
            service.reroute("runtime-1")

    def test_disabled_route(self):
        endpoint_service, health_service, service = _build()
        endpoint_service.add("endpoint-a", "runtime-1")
        endpoint_service.add("endpoint-b", "runtime-1")
        health_service.set_healthy("endpoint-a", True)
        health_service.set_healthy("endpoint-b", True)
        route_a = service.register("runtime-1", "endpoint-a", 2)
        route_b = service.register("runtime-1", "endpoint-b", 1)

        disabled = service.disable(route_b.route_id)
        assert disabled.status == "DISABLED"

        resolved = service.resolve("runtime-1")
        assert resolved.route_id == route_a.route_id

    def test_disable_is_idempotent(self):
        endpoint_service, health_service, service = _build()
        endpoint_service.add("endpoint-a", "runtime-1")
        health_service.set_healthy("endpoint-a", True)
        route = service.register("runtime-1", "endpoint-a", 1)

        first = service.disable(route.route_id)
        second = service.disable(route.route_id)

        assert second.route_id == first.route_id
        assert second.status == "DISABLED"

    def test_disable_unknown_route_is_rejected(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.disable("does-not-exist")

    def test_all_endpoints_unavailable(self):
        endpoint_service, health_service, service = _build()
        endpoint_service.add("endpoint-a", "runtime-1")
        endpoint_service.add("endpoint-b", "runtime-1")
        health_service.set_healthy("endpoint-a", False)
        health_service.set_healthy("endpoint-b", False)
        service.register("runtime-1", "endpoint-a", 1)
        service.register("runtime-1", "endpoint-b", 2)

        with pytest.raises(Error):
            service.resolve("runtime-1")

    def test_resolve_with_no_routes_is_rejected(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.resolve("runtime-1")

    def test_resolve_treats_health_check_error_as_unhealthy(self):
        endpoint_service, health_service, service = _build()
        endpoint_service.add("endpoint-a", "runtime-1")
        service.register("runtime-1", "endpoint-a", 1)

        with pytest.raises(Error):
            service.resolve("runtime-1")
