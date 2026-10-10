from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_runtime_state import (
    TERMINAL_STATES,
)

from .execution_network_endpoint import (
    ExecutionNetworkEndpoint,
    PROTOCOLS,
    STATUS_ACTIVE,
    STATUS_REMOVED,
)

from .execution_network_endpoint_error import (
    ExecutionNetworkEndpointError,
)


class ExecutionNetworkEndpointService:
    """
    Registers the network endpoints through which execution runtimes
    can communicate.

    Composes with an existing runtime state service (anything
    exposing `state(runtime_id) -> object with .state`, matching
    ExecutionRuntimeStateService), used to reject registration for
    runtimes that have already reached a terminal state (STOPPED,
    FAILED).

    Behavior:
    - register() admits a new ACTIVE endpoint, but only for a
      non-terminal runtime, with a valid address and port, a
      supported protocol, and only when the runtime holds no other
      ACTIVE endpoint for that protocol
    - remove() is idempotent: removing an already-removed endpoint
      simply returns it unchanged
    - get() reports a single endpoint by its ID
    - active() reports a runtime's currently-ACTIVE endpoints

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, state_service):
        self._state_service = state_service
        self._endpoints_by_id = {}
        self._lock = RLock()

    def register(self, runtime_id: str, address: str, port: int, protocol: str) -> ExecutionNetworkEndpoint:
        """
        Register a new endpoint for runtime_id.

        Raises:
            ExecutionNetworkEndpointError: If runtime_id or address is
                None or blank, port is not a valid port number,
                protocol is not one of PROTOCOLS, runtime_id is
                unknown or has reached a terminal state, or the
                runtime already holds an active endpoint for protocol
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(address, "address")
        self._validate_protocol(protocol)

        current_state = self._current_state(runtime_id)

        if current_state in TERMINAL_STATES:
            raise ExecutionNetworkEndpointError(
                f"Cannot register an endpoint for runtime ID {runtime_id!r}: "
                f"it has reached a terminal state ({current_state!r})."
            )

        with self._lock:
            for endpoint in self._endpoints_by_id.values():
                if (
                    endpoint.runtime_id == runtime_id
                    and endpoint.protocol == protocol
                    and endpoint.status == STATUS_ACTIVE
                ):
                    raise ExecutionNetworkEndpointError(
                        f"Cannot register an endpoint for runtime ID {runtime_id!r}: it already has "
                        f"an active {protocol!r} endpoint."
                    )

            endpoint = ExecutionNetworkEndpoint(
                endpoint_id=str(uuid4()),
                runtime_id=runtime_id,
                address=address,
                port=port,
                protocol=protocol,
                status=STATUS_ACTIVE,
            )

            self._endpoints_by_id[endpoint.endpoint_id] = endpoint

            return endpoint

    def remove(self, endpoint_id: str) -> ExecutionNetworkEndpoint:
        """
        Remove an endpoint. Idempotent: removing an already-removed
        endpoint simply returns it unchanged.

        Raises:
            ExecutionNetworkEndpointError: If endpoint_id is None or
                blank, or no endpoint is registered under it
        """

        self._validate_text(endpoint_id, "endpoint ID")

        with self._lock:
            endpoint = self._resolve(endpoint_id)

            if endpoint.status == STATUS_REMOVED:
                return endpoint

            removed = replace(endpoint, status=STATUS_REMOVED)
            self._endpoints_by_id[endpoint_id] = removed

            return removed

    def get(self, endpoint_id: str) -> ExecutionNetworkEndpoint:
        """
        The endpoint registered under endpoint_id.

        Raises:
            ExecutionNetworkEndpointError: If endpoint_id is None or
                blank, or no endpoint is registered under it
        """

        self._validate_text(endpoint_id, "endpoint ID")

        with self._lock:
            return self._resolve(endpoint_id)

    def active(self, runtime_id: str) -> tuple:
        """
        The currently-ACTIVE endpoints registered for runtime_id.
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            return tuple(
                endpoint
                for endpoint in self._endpoints_by_id.values()
                if endpoint.runtime_id == runtime_id and endpoint.status == STATUS_ACTIVE
            )

    def _current_state(self, runtime_id: str) -> str:
        try:
            return self._state_service.state(runtime_id).state
        except Exception as error:
            raise ExecutionNetworkEndpointError(
                f"Cannot resolve runtime ID {runtime_id!r}: it is unknown."
            ) from error

    def _resolve(self, endpoint_id: str) -> ExecutionNetworkEndpoint:
        endpoint = self._endpoints_by_id.get(endpoint_id)

        if endpoint is None:
            raise ExecutionNetworkEndpointError(
                f"No endpoint is registered under endpoint ID {endpoint_id!r}."
            )

        return endpoint

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkEndpointError(f"Cannot use an empty or blank {field_name}.")

    @staticmethod
    def _validate_protocol(protocol: str) -> None:
        if protocol not in PROTOCOLS:
            raise ExecutionNetworkEndpointError(f"Cannot use an unknown protocol: {protocol!r}.")
