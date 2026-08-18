from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from numbers import (
    Integral,
)

from .execution_network_circuit_error import (
    ExecutionNetworkCircuitError,
)

STATE_CLOSED = "CLOSED"

STATE_OPEN = "OPEN"

STATE_HALF_OPEN = "HALF_OPEN"

STATES = (
    STATE_CLOSED,
    STATE_OPEN,
    STATE_HALF_OPEN,
)


@dataclass(frozen=True)
class ExecutionNetworkCircuit:
    """
    Immutable snapshot of whether an endpoint's traffic is currently
    permitted, tripped, or being cautiously retried.

    The circuit is a value object only. It performs no failure
    counting or state transition logic of its own; deciding when to
    open, retry, or close a circuit is the responsibility of an
    execution network circuit breaker service, which produces a new
    snapshot for every transition rather than mutating an existing
    one.

    Attributes:
        circuit_id: The circuit's unique identifier
        endpoint_id: The identifier of the endpoint this circuit
            guards
        failure_count: How many consecutive failures have been
            recorded since the circuit last closed
        threshold: How many failures trip the circuit open
        state: The circuit's current state, one of STATES
        opened_at: When the circuit last tripped open, or None while
            CLOSED
    """

    circuit_id: str

    endpoint_id: str

    failure_count: int

    threshold: int

    state: str

    opened_at: datetime = None

    def __post_init__(self):
        self._require_text(self.circuit_id, "circuit ID")
        self._require_text(self.endpoint_id, "endpoint ID")

        if (
            self.failure_count is None
            or isinstance(self.failure_count, bool)
            or not isinstance(self.failure_count, Integral)
            or self.failure_count < 0
        ):
            raise ExecutionNetworkCircuitError(
                f"Cannot build an execution network circuit with a negative failure_count: "
                f"{self.failure_count!r}."
            )

        if (
            self.threshold is None
            or isinstance(self.threshold, bool)
            or not isinstance(self.threshold, Integral)
            or self.threshold < 1
        ):
            raise ExecutionNetworkCircuitError(
                f"Cannot build an execution network circuit with a threshold below 1: "
                f"{self.threshold!r}."
            )

        if self.state not in STATES:
            raise ExecutionNetworkCircuitError(
                f"Cannot build an execution network circuit with an unknown state: {self.state!r}."
            )

        if self.state == STATE_CLOSED and self.opened_at is not None:
            raise ExecutionNetworkCircuitError(
                "Cannot build an execution network circuit with an opened_at while CLOSED."
            )

        if self.state != STATE_CLOSED and (
            self.opened_at is None or not isinstance(self.opened_at, datetime)
        ):
            raise ExecutionNetworkCircuitError(
                f"Cannot build an execution network circuit in state {self.state!r} without a "
                f"datetime opened_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkCircuitError(
                f"Cannot build an execution network circuit with an empty or blank {field_name}."
            )
