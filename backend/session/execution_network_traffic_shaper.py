from dataclasses import (
    dataclass,
)

from numbers import (
    Real,
)

from .execution_network_traffic_policy import (
    DIRECTIONS,
)

from .execution_network_traffic_shaper_error import (
    ExecutionNetworkTrafficShaperError,
)


@dataclass(frozen=True)
class ExecutionNetworkTrafficShaper:
    """
    Immutable record of the rate a runtime's traffic in one direction
    is held to.

    The shaper is a value object only. It performs no token
    accounting of its own; enforcing rate_limit and burst_limit
    against traffic is the responsibility of an execution network
    traffic shaping service, which produces a new record for every
    reconfiguration rather than mutating an existing one.

    Attributes:
        shaper_id: The shaper's unique identifier
        runtime_id: The identifier of the runtime this shaper governs
        direction: Which way the traffic flows, one of DIRECTIONS
        rate_limit: The sustained amount of traffic permitted per
            second
        burst_limit: The maximum amount of traffic that may be sent
            at once, above the sustained rate
        enabled: Whether this shaper is currently enforced
    """

    shaper_id: str

    runtime_id: str

    direction: str

    rate_limit: float

    burst_limit: float

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.shaper_id, "shaper ID")
        self._require_text(self.runtime_id, "runtime ID")

        if self.direction not in DIRECTIONS:
            raise ExecutionNetworkTrafficShaperError(
                f"Cannot build an execution network traffic shaper with an unknown direction: "
                f"{self.direction!r}."
            )

        self._require_positive(self.rate_limit, "rate_limit")
        self._require_positive(self.burst_limit, "burst_limit")

        if not isinstance(self.enabled, bool):
            raise ExecutionNetworkTrafficShaperError(
                f"Cannot build an execution network traffic shaper with a non-boolean enabled: "
                f"{self.enabled!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkTrafficShaperError(
                f"Cannot build an execution network traffic shaper with an empty or blank {field_name}."
            )

    @staticmethod
    def _require_positive(value, field_name: str) -> None:
        if value is None or isinstance(value, bool) or not isinstance(value, Real) or value <= 0:
            raise ExecutionNetworkTrafficShaperError(
                f"Cannot build an execution network traffic shaper with a non-positive {field_name}: "
                f"{value!r}."
            )
