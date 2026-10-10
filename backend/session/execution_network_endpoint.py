from dataclasses import (
    dataclass,
)

from numbers import (
    Integral,
)

from .execution_network_endpoint_error import (
    ExecutionNetworkEndpointError,
)

PROTOCOL_HTTP = "HTTP"

PROTOCOL_HTTPS = "HTTPS"

PROTOCOL_TCP = "TCP"

PROTOCOLS = (
    PROTOCOL_HTTP,
    PROTOCOL_HTTPS,
    PROTOCOL_TCP,
)

STATUS_ACTIVE = "ACTIVE"

STATUS_REMOVED = "REMOVED"

STATUSES = (
    STATUS_ACTIVE,
    STATUS_REMOVED,
)

MIN_PORT = 1

MAX_PORT = 65535


@dataclass(frozen=True)
class ExecutionNetworkEndpoint:
    """
    Immutable record of a network endpoint through which a runtime
    can be reached.

    The endpoint is a value object only. It performs no registration
    accounting of its own; registering and removing endpoints is the
    responsibility of an execution network endpoint service, which
    produces a new record for every transition rather than mutating
    an existing one.

    Attributes:
        endpoint_id: The endpoint's unique identifier
        runtime_id: The identifier of the runtime this endpoint
            belongs to
        address: The network address the endpoint is reachable at
        port: The network port the endpoint is reachable at
        protocol: The endpoint's protocol, one of PROTOCOLS
        status: The endpoint's current state, one of STATUSES
    """

    endpoint_id: str

    runtime_id: str

    address: str

    port: int

    protocol: str

    status: str = STATUS_ACTIVE

    def __post_init__(self):
        self._require_text(self.endpoint_id, "endpoint ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.address, "address")

        if (
            self.port is None
            or isinstance(self.port, bool)
            or not isinstance(self.port, Integral)
            or not (MIN_PORT <= self.port <= MAX_PORT)
        ):
            raise ExecutionNetworkEndpointError(
                f"Cannot build an execution network endpoint with an invalid port: {self.port!r}."
            )

        if self.protocol not in PROTOCOLS:
            raise ExecutionNetworkEndpointError(
                f"Cannot build an execution network endpoint with an unknown protocol: "
                f"{self.protocol!r}."
            )

        if self.status not in STATUSES:
            raise ExecutionNetworkEndpointError(
                f"Cannot build an execution network endpoint with an unknown status: {self.status!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkEndpointError(
                f"Cannot build an execution network endpoint with an empty or blank {field_name}."
            )
