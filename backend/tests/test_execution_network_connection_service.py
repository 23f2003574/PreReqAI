import pytest

from backend.session import (
    ExecutionNetworkConnection,
    ExecutionNetworkConnectionError as Error,
    ExecutionNetworkConnectionService,
)


class _FakeStateRecord:
    def __init__(self, state):
        self.state = state


class _FakeStateService:
    def __init__(self, state_by_runtime=None):
        self._state_by_runtime = dict(state_by_runtime or {})

    def state(self, runtime_id):
        if runtime_id not in self._state_by_runtime:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return _FakeStateRecord(self._state_by_runtime[runtime_id])

    def set_state(self, runtime_id, state):
        self._state_by_runtime[runtime_id] = state


class _FakeEndpoint:
    def __init__(self, endpoint_id, runtime_id, status):
        self.endpoint_id = endpoint_id
        self.runtime_id = runtime_id
        self.status = status


class _FakeEndpointService:
    def __init__(self):
        self._endpoints = {}

    def add(self, endpoint_id, runtime_id, status="ACTIVE"):
        self._endpoints[endpoint_id] = _FakeEndpoint(endpoint_id, runtime_id, status)

    def set_status(self, endpoint_id, status):
        endpoint = self._endpoints[endpoint_id]
        self._endpoints[endpoint_id] = _FakeEndpoint(endpoint_id, endpoint.runtime_id, status)

    def get(self, endpoint_id):
        if endpoint_id not in self._endpoints:
            raise ValueError(f"unknown endpoint {endpoint_id!r}")

        return self._endpoints[endpoint_id]


def _build(state_by_runtime=None):
    state_service = _FakeStateService(
        state_by_runtime or {"runtime-1": "RUNNING", "runtime-2": "RUNNING"}
    )
    endpoint_service = _FakeEndpointService()
    service = ExecutionNetworkConnectionService(state_service, endpoint_service)

    return state_service, endpoint_service, service


class TestExecutionNetworkConnectionService:
    def test_open_and_close(self):
        state_service, endpoint_service, service = _build()
        endpoint_service.add("endpoint-1", "runtime-1")

        connection = service.open("runtime-1", "endpoint-1")

        assert isinstance(connection, ExecutionNetworkConnection)
        assert connection.status == "OPEN"
        assert connection.closed_at is None
        assert service.status(connection.connection_id) == "OPEN"

        closed = service.close(connection.connection_id)

        assert closed.status == "CLOSED"
        assert closed.closed_at is not None
        assert service.status(connection.connection_id) == "CLOSED"
        assert service.active("runtime-1") == ()

    def test_duplicate_connection_rejection(self):
        _, endpoint_service, service = _build()
        endpoint_service.add("endpoint-1", "runtime-1")
        service.open("runtime-1", "endpoint-1")

        with pytest.raises(Error):
            service.open("runtime-1", "endpoint-1")

    def test_inactive_endpoint_rejection(self):
        _, endpoint_service, service = _build()
        endpoint_service.add("endpoint-1", "runtime-1", status="REMOVED")

        with pytest.raises(Error):
            service.open("runtime-1", "endpoint-1")

    def test_inactive_runtime_rejection(self):
        state_service, endpoint_service, service = _build()
        endpoint_service.add("endpoint-1", "runtime-1")
        state_service.set_state("runtime-1", "STOPPED")

        with pytest.raises(Error):
            service.open("runtime-1", "endpoint-1")

    def test_mismatched_runtime_rejection(self):
        _, endpoint_service, service = _build()
        endpoint_service.add("endpoint-1", "runtime-2")

        with pytest.raises(Error):
            service.open("runtime-1", "endpoint-1")

    def test_runtime_isolation(self):
        _, endpoint_service, service = _build()
        endpoint_service.add("endpoint-1", "runtime-1")
        endpoint_service.add("endpoint-2", "runtime-2")
        service.open("runtime-1", "endpoint-1")
        service.open("runtime-2", "endpoint-2")

        assert len(service.active("runtime-1")) == 1
        assert len(service.active("runtime-2")) == 1
        assert service.active("runtime-1")[0].runtime_id == "runtime-1"
        assert service.active("runtime-2")[0].runtime_id == "runtime-2"

    def test_cleanup(self):
        _, endpoint_service, service = _build()
        endpoint_service.add("endpoint-1", "runtime-1")
        endpoint_service.add("endpoint-2", "runtime-1")
        service.open("runtime-1", "endpoint-1")
        service.open("runtime-1", "endpoint-2")

        closed = service.cleanup("runtime-1")

        assert len(closed) == 2
        assert all(connection.status == "CLOSED" for connection in closed)
        assert service.active("runtime-1") == ()

    def test_cleanup_is_idempotent(self):
        _, endpoint_service, service = _build()
        endpoint_service.add("endpoint-1", "runtime-1")
        service.open("runtime-1", "endpoint-1")
        service.cleanup("runtime-1")

        assert service.cleanup("runtime-1") == ()

    def test_closed_state_protection(self):
        _, endpoint_service, service = _build()
        endpoint_service.add("endpoint-1", "runtime-1")
        connection = service.open("runtime-1", "endpoint-1")
        service.close(connection.connection_id)

        with pytest.raises(Error):
            service.close(connection.connection_id)

    def test_status_of_unknown_connection_is_rejected(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.status("does-not-exist")

    def test_close_unknown_connection_is_rejected(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.close("does-not-exist")
