import math

import pytest

from backend.session import (
    ExecutionNetworkDecision,
    ExecutionNetworkDecisionError as Error,
    ExecutionNetworkOrchestrationService,
)


class _FakeEndpoint:
    def __init__(self, protocol):
        self.protocol = protocol


class _FakeEndpointService:
    def __init__(self):
        self._endpoints = {}

    def add(self, endpoint_id, protocol="HTTP"):
        self._endpoints[endpoint_id] = _FakeEndpoint(protocol)

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
        return self._healthy.get(endpoint_id, True)


class _FakeCircuitService:
    def __init__(self):
        self._allowed = {}

    def set_allow(self, endpoint_id, value):
        self._allowed[endpoint_id] = value

    def allow(self, endpoint_id):
        return self._allowed.get(endpoint_id, True)


class _FakeTrafficPolicyService:
    def __init__(self):
        self._denied = set()

    def deny(self, endpoint_id):
        self._denied.add(endpoint_id)

    def evaluate(self, runtime_id, endpoint_id, direction, protocol):
        return endpoint_id not in self._denied


class _FakeConnectionLimitService:
    def __init__(self):
        self._can_open = {}
        self.acquired = []
        self.released = []

    def set_can_open(self, runtime_id, value):
        self._can_open[runtime_id] = value

    def can_open(self, runtime_id):
        return self._can_open.get(runtime_id, True)

    def acquire(self, runtime_id, connection_id):
        self.acquired.append((runtime_id, connection_id))

    def release(self, runtime_id, connection_id):
        self.released.append((runtime_id, connection_id))


class _FakeConnection:
    def __init__(self, connection_id, runtime_id, endpoint_id):
        self.connection_id = connection_id
        self.runtime_id = runtime_id
        self.endpoint_id = endpoint_id


class _FakeConnectionService:
    def __init__(self):
        self._counter = 0
        self._open_by_runtime = {}

    def open(self, runtime_id, endpoint_id):
        self._counter += 1
        connection = _FakeConnection(f"connection-{self._counter}", runtime_id, endpoint_id)
        self._open_by_runtime.setdefault(runtime_id, []).append(connection)

        return connection

    def close(self, connection_id):
        for connections in self._open_by_runtime.values():
            connections[:] = [c for c in connections if c.connection_id != connection_id]

    def cleanup(self, runtime_id):
        closed = tuple(self._open_by_runtime.get(runtime_id, ()))
        self._open_by_runtime[runtime_id] = []

        return closed

    def open_connections(self, runtime_id):
        return tuple(self._open_by_runtime.get(runtime_id, ()))


class _FakeQuotaService:
    def __init__(self):
        self._available = {}

    def set_available(self, runtime_id, direction, value):
        self._available[(runtime_id, direction)] = value

    def available(self, runtime_id, direction):
        return self._available.get((runtime_id, direction), math.inf)

    def consume(self, runtime_id, direction, amount):
        pass


class _FakeShapingService:
    def __init__(self):
        self._remaining = {}

    def set_remaining(self, runtime_id, direction, value):
        self._remaining[(runtime_id, direction)] = value

    def remaining(self, runtime_id, direction):
        return self._remaining.get((runtime_id, direction), math.inf)

    def allow(self, runtime_id, direction, amount):
        return True


class _FakeFailoverRecord:
    def __init__(self, selected_endpoint):
        self.selected_endpoint = selected_endpoint


class _FakeFailoverService:
    def __init__(self):
        self._select = {}
        self._execute = {}

    def set_select(self, runtime_id, endpoint_id):
        self._select[runtime_id] = endpoint_id

    def set_execute(self, runtime_id, endpoint_id):
        self._execute[runtime_id] = endpoint_id

    def select(self, runtime_id):
        if runtime_id not in self._select:
            raise ValueError(f"no endpoints registered for {runtime_id!r}")

        return self._select[runtime_id]

    def execute(self, runtime_id):
        if runtime_id in self._execute:
            return _FakeFailoverRecord(self._execute[runtime_id])

        if runtime_id in self._select:
            return _FakeFailoverRecord(self._select[runtime_id])

        raise ValueError(f"no endpoints registered for {runtime_id!r}")


class _FakeFailoverPolicyService:
    def __init__(self):
        self._triggered = {}

    def set_triggered(self, runtime_id, triggered):
        self._triggered[runtime_id] = triggered

    def evaluate(self, runtime_id):
        return self._triggered.get(runtime_id, ())


def _build():
    endpoint_service = _FakeEndpointService()
    health_service = _FakeHealthService()
    circuit_service = _FakeCircuitService()
    traffic_policy_service = _FakeTrafficPolicyService()
    connection_limit_service = _FakeConnectionLimitService()
    connection_service = _FakeConnectionService()
    quota_service = _FakeQuotaService()
    shaping_service = _FakeShapingService()
    failover_service = _FakeFailoverService()
    failover_policy_service = _FakeFailoverPolicyService()

    service = ExecutionNetworkOrchestrationService(
        endpoint_service,
        health_service,
        circuit_service,
        traffic_policy_service,
        connection_limit_service,
        connection_service,
        quota_service,
        shaping_service,
        failover_service,
        failover_policy_service,
    )

    return {
        "endpoint": endpoint_service,
        "health": health_service,
        "circuit": circuit_service,
        "policy": traffic_policy_service,
        "limit": connection_limit_service,
        "connection": connection_service,
        "quota": quota_service,
        "shaping": shaping_service,
        "failover": failover_service,
        "failover_policy": failover_policy_service,
        "service": service,
    }


class TestExecutionNetworkOrchestrationService:
    def test_successful_connection(self):
        f = _build()
        f["endpoint"].add("endpoint-1", "HTTP")
        f["failover"].set_select("runtime-1", "endpoint-1")

        decision = f["service"].connect("runtime-1")

        assert isinstance(decision, ExecutionNetworkDecision)
        assert decision.allowed is True
        assert decision.endpoint_id == "endpoint-1"
        assert decision.reason == "connected"
        assert len(f["connection"].open_connections("runtime-1")) == 1
        assert len(f["limit"].acquired) == 1

    def test_policy_denial(self):
        f = _build()
        f["endpoint"].add("endpoint-1", "HTTP")
        f["failover"].set_select("runtime-1", "endpoint-1")
        f["policy"].deny("endpoint-1")

        decision = f["service"].connect("runtime-1")

        assert decision.allowed is False
        assert decision.reason == "traffic policy denied"
        assert f["connection"].open_connections("runtime-1") == ()

    def test_quota_blocking(self):
        f = _build()
        f["endpoint"].add("endpoint-1", "HTTP")
        f["failover"].set_select("runtime-1", "endpoint-1")
        f["quota"].set_available("runtime-1", "EGRESS", 0)

        decision = f["service"].connect("runtime-1")

        assert decision.allowed is False
        assert decision.reason == "quota exceeded"
        assert f["connection"].open_connections("runtime-1") == ()

    def test_circuit_failover(self):
        f = _build()
        f["endpoint"].add("endpoint-1", "HTTP")
        f["endpoint"].add("endpoint-2", "HTTP")
        f["circuit"].set_allow("endpoint-1", False)
        f["failover"].set_select("runtime-1", "endpoint-2")

        decision = f["service"].connect("runtime-1")

        assert decision.allowed is True
        assert decision.endpoint_id == "endpoint-2"

    def test_endpoint_failover(self):
        f = _build()
        f["endpoint"].add("endpoint-1", "HTTP")
        f["endpoint"].add("endpoint-2", "HTTP")
        f["health"].set_healthy("endpoint-1", False)
        f["failover"].set_select("runtime-1", "endpoint-2")

        decision = f["service"].connect("runtime-1")

        assert decision.allowed is True
        assert decision.endpoint_id == "endpoint-2"

    def test_connection_limit_blocking(self):
        f = _build()
        f["endpoint"].add("endpoint-1", "HTTP")
        f["failover"].set_select("runtime-1", "endpoint-1")
        f["limit"].set_can_open("runtime-1", False)

        decision = f["service"].connect("runtime-1")

        assert decision.allowed is False
        assert decision.reason == "connection limit exceeded"
        assert f["connection"].open_connections("runtime-1") == ()

    def test_deterministic_decision(self):
        f = _build()
        f["endpoint"].add("endpoint-1", "HTTP")

        results = [f["service"].evaluate("runtime-1", "endpoint-1") for _ in range(5)]

        assert all(r.allowed is True and r.endpoint_id == "endpoint-1" and r.reason == "allowed" for r in results)

    def test_evaluate_does_not_open_connection(self):
        f = _build()
        f["endpoint"].add("endpoint-1", "HTTP")

        decision = f["service"].evaluate("runtime-1", "endpoint-1")

        assert decision.allowed is True
        assert f["connection"].open_connections("runtime-1") == ()
        assert f["limit"].acquired == []

    def test_no_endpoint_available(self):
        f = _build()

        decision = f["service"].connect("runtime-1")

        assert decision.allowed is False
        assert decision.reason == "no endpoint available"
        assert decision.endpoint_id is None

    def test_disconnect_closes_connections_and_releases_limit(self):
        f = _build()
        f["endpoint"].add("endpoint-1", "HTTP")
        f["failover"].set_select("runtime-1", "endpoint-1")
        f["service"].connect("runtime-1")

        decision = f["service"].disconnect("runtime-1")

        assert decision.allowed is False
        assert decision.reason == "disconnected"
        assert f["connection"].open_connections("runtime-1") == ()
        assert len(f["limit"].released) == 1

    def test_reroute_reconnects_via_failover_execute(self):
        f = _build()
        f["endpoint"].add("endpoint-1", "HTTP")
        f["endpoint"].add("endpoint-2", "HTTP")
        f["failover"].set_select("runtime-1", "endpoint-1")
        f["service"].connect("runtime-1")

        f["failover"].set_execute("runtime-1", "endpoint-2")
        decision = f["service"].reroute("runtime-1")

        assert decision.allowed is True
        assert decision.endpoint_id == "endpoint-2"
        assert len(f["connection"].open_connections("runtime-1")) == 1

    def test_decision_lookup(self):
        f = _build()
        f["endpoint"].add("endpoint-1", "HTTP")
        f["failover"].set_select("runtime-1", "endpoint-1")
        connected = f["service"].connect("runtime-1")

        assert f["service"].decision("runtime-1").decision_id == connected.decision_id

    def test_decision_lookup_without_history_is_rejected(self):
        f = _build()

        with pytest.raises(Error):
            f["service"].decision("runtime-1")

    def test_validation_rejects_blank_runtime_id(self):
        f = _build()

        with pytest.raises(Error):
            f["service"].connect("")

        with pytest.raises(Error):
            f["service"].evaluate("runtime-1", "")
