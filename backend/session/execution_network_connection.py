from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_network_connection_error import (
    ExecutionNetworkConnectionError,
)

STATUS_OPEN = "OPEN"

STATUS_CLOSED = "CLOSED"

STATUSES = (
    STATUS_OPEN,
    STATUS_CLOSED,
)


@dataclass(frozen=True)
class ExecutionNetworkConnection:
    """
    Immutable record of an active (or previously active) network
    connection between a runtime and one of its endpoints.

    The connection is a value object only. It performs no connection
    accounting of its own; opening, closing, and cleaning up
    connections is the responsibility of an execution network
    connection service, which produces a new record for every
    transition rather than mutating an existing one.

    Attributes:
        connection_id: The connection's unique identifier
        runtime_id: The identifier of the runtime this connection
            belongs to
        endpoint_id: The identifier of the endpoint this connection
            was opened to
        status: The connection's current state, one of STATUSES
        opened_at: When the connection was opened
        closed_at: When the connection was closed, or None if it is
            still open
    """

    connection_id: str

    runtime_id: str

    endpoint_id: str

    status: str = STATUS_OPEN

    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    closed_at: datetime = None

    def __post_init__(self):
        self._require_text(self.connection_id, "connection ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.endpoint_id, "endpoint ID")

        if self.status not in STATUSES:
            raise ExecutionNetworkConnectionError(
                f"Cannot build an execution network connection with an unknown status: {self.status!r}."
            )

        if self.opened_at is None or not isinstance(self.opened_at, datetime):
            raise ExecutionNetworkConnectionError(
                "Cannot build an execution network connection with a non-datetime opened_at."
            )

        if self.closed_at is not None and not isinstance(self.closed_at, datetime):
            raise ExecutionNetworkConnectionError(
                "Cannot build an execution network connection with a non-datetime closed_at."
            )

        if self.status == STATUS_OPEN and self.closed_at is not None:
            raise ExecutionNetworkConnectionError(
                "Cannot build an execution network connection with a closed_at for an OPEN connection."
            )

        if self.status == STATUS_CLOSED and self.closed_at is None:
            raise ExecutionNetworkConnectionError(
                "Cannot build an execution network connection with no closed_at for a CLOSED connection."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkConnectionError(
                f"Cannot build an execution network connection with an empty or blank {field_name}."
            )
