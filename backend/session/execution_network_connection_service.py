from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_network_endpoint import (
    STATUS_ACTIVE as ENDPOINT_STATUS_ACTIVE,
)

from .execution_network_connection import (
    ExecutionNetworkConnection,
    STATUS_CLOSED,
    STATUS_OPEN,
)

from .execution_network_connection_error import (
    ExecutionNetworkConnectionError,
)

RUNTIME_ACTIVE_STATES = ("RUNNING", "PAUSED")


class ExecutionNetworkConnectionService:
    """
    Tracks active network connections between execution runtimes and
    their endpoints.

    Composes with:
        state_service: state(runtime_id) -> object with .state
            (ExecutionRuntimeStateService)
        endpoint_service: get(endpoint_id) -> object with
            .runtime_id, .status (ExecutionNetworkEndpointService)

    Behavior:
    - open() admits a new OPEN connection, but only for a runtime
      whose current state is RUNNING or PAUSED and an endpoint that
      is currently ACTIVE and belongs to that runtime, and only when
      the runtime holds no other OPEN connection to that endpoint
    - close() moves an OPEN connection to CLOSED, but a connection
      that is already CLOSED is immutable: closing it again is
      rejected outright
    - cleanup() closes every remaining OPEN connection held by a
      runtime
    - active() reports a runtime's currently-OPEN connections
    - status() reports a single connection's current status

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, state_service, endpoint_service):
        self._state_service = state_service
        self._endpoint_service = endpoint_service
        self._connections_by_id = {}
        self._lock = RLock()

    def open(self, runtime_id: str, endpoint_id: str) -> ExecutionNetworkConnection:
        """
        Open a new connection from runtime_id to endpoint_id.

        Raises:
            ExecutionNetworkConnectionError: If runtime_id or
                endpoint_id is None or blank, runtime_id is unknown
                or not RUNNING or PAUSED, endpoint_id is unknown, not
                ACTIVE, or belongs to a different runtime, or the
                runtime already holds an open connection to that
                endpoint
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(endpoint_id, "endpoint ID")

        current_state = self._current_runtime_state(runtime_id)

        if current_state not in RUNTIME_ACTIVE_STATES:
            raise ExecutionNetworkConnectionError(
                f"Cannot open a connection for runtime ID {runtime_id!r}: it is not active "
                f"(state is {current_state!r})."
            )

        endpoint = self._resolve_endpoint(endpoint_id)

        if endpoint.runtime_id != runtime_id:
            raise ExecutionNetworkConnectionError(
                f"Cannot open a connection for runtime ID {runtime_id!r}: endpoint ID "
                f"{endpoint_id!r} belongs to a different runtime."
            )

        if endpoint.status != ENDPOINT_STATUS_ACTIVE:
            raise ExecutionNetworkConnectionError(
                f"Cannot open a connection to endpoint ID {endpoint_id!r}: it is not active "
                f"(status is {endpoint.status!r})."
            )

        with self._lock:
            for connection in self._connections_by_id.values():
                if (
                    connection.runtime_id == runtime_id
                    and connection.endpoint_id == endpoint_id
                    and connection.status == STATUS_OPEN
                ):
                    raise ExecutionNetworkConnectionError(
                        f"Cannot open a connection for runtime ID {runtime_id!r}: it already has "
                        f"an open connection to endpoint ID {endpoint_id!r}."
                    )

            connection = ExecutionNetworkConnection(
                connection_id=str(uuid4()),
                runtime_id=runtime_id,
                endpoint_id=endpoint_id,
                status=STATUS_OPEN,
                opened_at=datetime.now(timezone.utc),
                closed_at=None,
            )

            self._connections_by_id[connection.connection_id] = connection

            return connection

    def close(self, connection_id: str) -> ExecutionNetworkConnection:
        """
        Close an open connection.

        Raises:
            ExecutionNetworkConnectionError: If connection_id is None
                or blank, no connection is registered under it, or it
                is already CLOSED
        """

        self._validate_text(connection_id, "connection ID")

        with self._lock:
            connection = self._resolve(connection_id)

            if connection.status == STATUS_CLOSED:
                raise ExecutionNetworkConnectionError(
                    f"Cannot close connection ID {connection_id!r}: it is already closed."
                )

            closed = replace(
                connection,
                status=STATUS_CLOSED,
                closed_at=datetime.now(timezone.utc),
            )
            self._connections_by_id[connection_id] = closed

            return closed

    def active(self, runtime_id: str) -> tuple:
        """
        The currently-OPEN connections held by runtime_id.
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            return tuple(
                connection
                for connection in self._connections_by_id.values()
                if connection.runtime_id == runtime_id and connection.status == STATUS_OPEN
            )

    def status(self, connection_id: str) -> str:
        """
        The current status of connection_id.

        Raises:
            ExecutionNetworkConnectionError: If connection_id is None
                or blank, or no connection is registered under it
        """

        self._validate_text(connection_id, "connection ID")

        with self._lock:
            return self._resolve(connection_id).status

    def cleanup(self, runtime_id: str) -> tuple:
        """
        Close every remaining OPEN connection held by runtime_id.

        Raises:
            ExecutionNetworkConnectionError: If runtime_id is None or
                blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            closed = []

            for connection_id, connection in list(self._connections_by_id.items()):
                if connection.runtime_id == runtime_id and connection.status == STATUS_OPEN:
                    closed.append(self.close(connection_id))

            return tuple(closed)

    def _current_runtime_state(self, runtime_id: str) -> str:
        try:
            return self._state_service.state(runtime_id).state
        except Exception as error:
            raise ExecutionNetworkConnectionError(
                f"Cannot resolve runtime ID {runtime_id!r}: it is unknown."
            ) from error

    def _resolve_endpoint(self, endpoint_id: str):
        try:
            return self._endpoint_service.get(endpoint_id)
        except Exception as error:
            raise ExecutionNetworkConnectionError(
                f"Cannot resolve endpoint ID {endpoint_id!r}: it is unknown."
            ) from error

    def _resolve(self, connection_id: str) -> ExecutionNetworkConnection:
        connection = self._connections_by_id.get(connection_id)

        if connection is None:
            raise ExecutionNetworkConnectionError(
                f"No connection is registered under connection ID {connection_id!r}."
            )

        return connection

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkConnectionError(f"Cannot use an empty or blank {field_name}.")
