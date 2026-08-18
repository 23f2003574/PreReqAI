import pytest

from backend.session import (
    ExecutionNetworkEndpoint,
    ExecutionNetworkEndpointError as Error,
    ExecutionNetworkEndpointService,
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


def _build(state_by_runtime=None):
    state_service = _FakeStateService(
        state_by_runtime or {"runtime-1": "RUNNING", "runtime-2": "RUNNING"}
    )
    return state_service, ExecutionNetworkEndpointService(state_service)


class TestExecutionNetworkEndpointService:
    def test_register_and_get(self):
        _, service = _build()

        endpoint = service.register("runtime-1", "10.0.0.1", 8080, "HTTP")

        assert isinstance(endpoint, ExecutionNetworkEndpoint)
        assert endpoint.status == "ACTIVE"
        assert service.get(endpoint.endpoint_id).endpoint_id == endpoint.endpoint_id

    def test_protocol_isolation(self):
        _, service = _build()

        http_endpoint = service.register("runtime-1", "10.0.0.1", 80, "HTTP")
        https_endpoint = service.register("runtime-1", "10.0.0.1", 443, "HTTPS")
        tcp_endpoint = service.register("runtime-1", "10.0.0.1", 9000, "TCP")

        active = service.active("runtime-1")

        assert {endpoint.endpoint_id for endpoint in active} == {
            http_endpoint.endpoint_id,
            https_endpoint.endpoint_id,
            tcp_endpoint.endpoint_id,
        }

    def test_duplicate_endpoint_rejection(self):
        _, service = _build()
        service.register("runtime-1", "10.0.0.1", 8080, "HTTP")

        with pytest.raises(Error):
            service.register("runtime-1", "10.0.0.2", 9090, "HTTP")

    def test_terminal_runtime_rejection(self):
        _, service = _build(state_by_runtime={"runtime-1": "STOPPED"})

        with pytest.raises(Error):
            service.register("runtime-1", "10.0.0.1", 8080, "HTTP")

    def test_invalid_address_and_port_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.register("runtime-1", "", 8080, "HTTP")

        with pytest.raises(Error):
            service.register("runtime-1", "10.0.0.1", 0, "HTTP")

        with pytest.raises(Error):
            service.register("runtime-1", "10.0.0.1", 70000, "HTTP")

        with pytest.raises(Error):
            service.register("runtime-1", "10.0.0.1", 8080, "FTP")

    def test_removal(self):
        _, service = _build()
        endpoint = service.register("runtime-1", "10.0.0.1", 8080, "HTTP")

        removed = service.remove(endpoint.endpoint_id)

        assert removed.status == "REMOVED"
        assert service.active("runtime-1") == ()

    def test_removal_is_idempotent(self):
        _, service = _build()
        endpoint = service.register("runtime-1", "10.0.0.1", 8080, "HTTP")
        first = service.remove(endpoint.endpoint_id)

        second = service.remove(endpoint.endpoint_id)

        assert second.endpoint_id == first.endpoint_id
        assert second.status == "REMOVED"

    def test_removed_endpoint_frees_protocol_for_reregistration(self):
        _, service = _build()
        endpoint = service.register("runtime-1", "10.0.0.1", 8080, "HTTP")
        service.remove(endpoint.endpoint_id)

        reregistered = service.register("runtime-1", "10.0.0.2", 9090, "HTTP")

        assert reregistered.endpoint_id != endpoint.endpoint_id
        assert service.active("runtime-1") == (reregistered,)

    def test_active_lookup(self):
        _, service = _build()
        service.register("runtime-1", "10.0.0.1", 8080, "HTTP")
        service.register("runtime-2", "10.0.0.2", 8081, "HTTP")

        assert len(service.active("runtime-1")) == 1
        assert len(service.active("runtime-2")) == 1
        assert service.active("runtime-1")[0].runtime_id == "runtime-1"

    def test_get_unknown_endpoint_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.get("does-not-exist")

    def test_remove_unknown_endpoint_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.remove("does-not-exist")

    def test_register_unknown_runtime_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.register("does-not-exist", "10.0.0.1", 8080, "HTTP")
