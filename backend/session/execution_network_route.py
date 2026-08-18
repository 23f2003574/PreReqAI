from dataclasses import (
    dataclass,
)

from numbers import (
    Integral,
)

from .execution_network_route_error import (
    ExecutionNetworkRouteError,
)

STATUS_ACTIVE = "ACTIVE"

STATUS_DISABLED = "DISABLED"

STATUSES = (
    STATUS_ACTIVE,
    STATUS_DISABLED,
)


@dataclass(frozen=True)
class ExecutionNetworkRoute:
    """
    Immutable record of a candidate path from a runtime to one of its
    registered endpoints.

    The route is a value object only. It performs no selection logic
    of its own; choosing among a runtime's routes by priority and
    endpoint health is the responsibility of an execution network
    routing service, which produces a new record for every transition
    rather than mutating an existing one.

    Attributes:
        route_id: The route's unique identifier
        runtime_id: The identifier of the runtime this route serves
        endpoint_id: The identifier of the endpoint this route leads
            to
        priority: The route's preference rank; a lower value wins
            over a higher one
        status: The route's current state, one of STATUSES
    """

    route_id: str

    runtime_id: str

    endpoint_id: str

    priority: int

    status: str = STATUS_ACTIVE

    def __post_init__(self):
        self._require_text(self.route_id, "route ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.endpoint_id, "endpoint ID")

        if (
            self.priority is None
            or isinstance(self.priority, bool)
            or not isinstance(self.priority, Integral)
            or self.priority < 0
        ):
            raise ExecutionNetworkRouteError(
                f"Cannot build an execution network route with an invalid priority: {self.priority!r}."
            )

        if self.status not in STATUSES:
            raise ExecutionNetworkRouteError(
                f"Cannot build an execution network route with an unknown status: {self.status!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkRouteError(
                f"Cannot build an execution network route with an empty or blank {field_name}."
            )
