import pytest

from backend.session import (
    ExecutionNetworkFailover,
    ExecutionNetworkFailoverError as Error,
    ExecutionNetworkFailoverService,
)


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


def _build():
    health_service = _FakeHealthService()
    circuit_service = _FakeCircuitService()
    service = ExecutionNetworkFailoverService(health_service, circuit_service)

    return health_service, circuit_service, service


def _endpoints(primary, backups):
    return {"primary": primary, "backups": backups}


class TestExecutionNetworkFailoverService:
    def test_primary_selection(self):
        _, _, service = _build()

        record = service.register("runtime-1", _endpoints("endpoint-1", ("endpoint-2",)))

        assert isinstance(record, ExecutionNetworkFailover)
        assert record.status == "PRIMARY"
        assert record.selected_endpoint == "endpoint-1"
        assert service.status("runtime-1") == "PRIMARY"

    def test_backup_failover(self):
        health_service, _, service = _build()
        service.register("runtime-1", _endpoints("endpoint-1", ("endpoint-2", "endpoint-3")))

        health_service.set_healthy("endpoint-1", False)
        record = service.execute("runtime-1")

        assert record.status == "FAILOVER"
        assert record.selected_endpoint == "endpoint-2"

    def test_unhealthy_endpoint_skip(self):
        health_service, _, service = _build()
        health_service.set_healthy("endpoint-1", False)

        record = service.register("runtime-1", _endpoints("endpoint-1", ("endpoint-2",)))

        assert record.status == "FAILOVER"
        assert record.selected_endpoint == "endpoint-2"

    def test_circuit_open_skip(self):
        _, circuit_service, service = _build()
        circuit_service.set_allow("endpoint-1", False)

        record = service.register("runtime-1", _endpoints("endpoint-1", ("endpoint-2",)))

        assert record.status == "FAILOVER"
        assert record.selected_endpoint == "endpoint-2"

    def test_all_endpoints_unavailable(self):
        health_service, _, service = _build()
        health_service.set_healthy("endpoint-1", False)
        health_service.set_healthy("endpoint-2", False)

        record = service.register("runtime-1", _endpoints("endpoint-1", ("endpoint-2",)))

        assert record.status == "FAILED"
        assert record.selected_endpoint is None

        with pytest.raises(Error):
            service.select("runtime-1")

    def test_deterministic_selection(self):
        health_service, _, service = _build()
        health_service.set_healthy("endpoint-1", False)
        service.register("runtime-1", _endpoints("endpoint-1", ("endpoint-2", "endpoint-3")))

        results = {service.select("runtime-1") for _ in range(10)}

        assert results == {"endpoint-2"}

    def test_select_returns_primary_when_healthy(self):
        _, _, service = _build()
        service.register("runtime-1", _endpoints("endpoint-1", ("endpoint-2",)))

        assert service.select("runtime-1") == "endpoint-1"

    def test_execute_without_registration_is_rejected(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.execute("runtime-1")

    def test_select_without_registration_is_rejected(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.select("runtime-1")

    def test_status_without_selection_is_rejected(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.status("runtime-1")

    def test_register_rejects_blank_primary(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.register("runtime-1", _endpoints("", ("endpoint-2",)))

    def test_runtime_isolation(self):
        health_service, _, service = _build()
        service.register("runtime-1", _endpoints("endpoint-1", ("endpoint-2",)))
        health_service.set_healthy("endpoint-3", False)
        service.register("runtime-2", _endpoints("endpoint-3", ("endpoint-4",)))

        assert service.status("runtime-1") == "PRIMARY"
        assert service.status("runtime-2") == "FAILOVER"
