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

from .execution_network_circuit import (
    ExecutionNetworkCircuit,
    STATE_CLOSED,
    STATE_HALF_OPEN,
    STATE_OPEN,
)

from .execution_network_circuit_error import (
    ExecutionNetworkCircuitError,
)

DEFAULT_FAILURE_THRESHOLD = 3

DEFAULT_RECOVERY_TIMEOUT_SECONDS = 30.0


class ExecutionNetworkCircuitBreakerService:
    """
    Stops repeatedly sending traffic to endpoints that are
    consistently failing.

    Every endpoint gets its own circuit, created CLOSED on first use
    with this service's configured threshold.

    Behavior:
    - record_failure() counts a failure; in CLOSED, reaching
      threshold trips the circuit OPEN; in HALF_OPEN, any failure
      reopens it immediately, resetting the recovery clock; a
      failure recorded while already OPEN is counted but changes
      nothing else
    - record_success() in HALF_OPEN closes the circuit and resets
      failure_count to 0; in CLOSED, it simply resets failure_count
      to 0; a success recorded while OPEN changes nothing
    - allow() reports whether traffic may currently be sent: always
      True while CLOSED, always True while HALF_OPEN (a cautious
      trial), and while OPEN it stays False until recovery_timeout_
      seconds have elapsed since opened_at, at which point the
      circuit moves to HALF_OPEN and one trial is allowed
    - open() and close() force a circuit's state directly, for manual
      intervention
    - state() reports a circuit's current stored state without
      evaluating recovery timing (only allow() does that)

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        recovery_timeout_seconds: float = DEFAULT_RECOVERY_TIMEOUT_SECONDS,
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout_seconds = recovery_timeout_seconds
        self._circuits_by_endpoint = {}
        self._lock = RLock()

    def record_failure(self, endpoint_id: str) -> ExecutionNetworkCircuit:
        """
        Record a failure for endpoint_id.

        Raises:
            ExecutionNetworkCircuitError: If endpoint_id is None or
                blank
        """

        self._validate_text(endpoint_id, "endpoint ID")

        with self._lock:
            circuit = self._resolve_or_create(endpoint_id)
            now = datetime.now(timezone.utc)

            if circuit.state == STATE_HALF_OPEN:
                circuit = replace(
                    circuit,
                    failure_count=circuit.failure_count + 1,
                    state=STATE_OPEN,
                    opened_at=now,
                )
            elif circuit.state == STATE_CLOSED:
                failure_count = circuit.failure_count + 1

                if failure_count >= circuit.threshold:
                    circuit = replace(
                        circuit, failure_count=failure_count, state=STATE_OPEN, opened_at=now
                    )
                else:
                    circuit = replace(circuit, failure_count=failure_count)
            else:
                circuit = replace(circuit, failure_count=circuit.failure_count + 1)

            self._circuits_by_endpoint[endpoint_id] = circuit

            return circuit

    def record_success(self, endpoint_id: str) -> ExecutionNetworkCircuit:
        """
        Record a success for endpoint_id.

        Raises:
            ExecutionNetworkCircuitError: If endpoint_id is None or
                blank
        """

        self._validate_text(endpoint_id, "endpoint ID")

        with self._lock:
            circuit = self._resolve_or_create(endpoint_id)

            if circuit.state == STATE_HALF_OPEN:
                circuit = replace(circuit, failure_count=0, state=STATE_CLOSED, opened_at=None)
            elif circuit.state == STATE_CLOSED:
                circuit = replace(circuit, failure_count=0)

            self._circuits_by_endpoint[endpoint_id] = circuit

            return circuit

    def allow(self, endpoint_id: str) -> bool:
        """
        Whether traffic may currently be sent to endpoint_id.

        Raises:
            ExecutionNetworkCircuitError: If endpoint_id is None or
                blank
        """

        self._validate_text(endpoint_id, "endpoint ID")

        with self._lock:
            circuit = self._resolve_or_create(endpoint_id)

            if circuit.state == STATE_CLOSED or circuit.state == STATE_HALF_OPEN:
                return True

            elapsed = (datetime.now(timezone.utc) - circuit.opened_at).total_seconds()

            if elapsed < self._recovery_timeout_seconds:
                return False

            circuit = replace(circuit, state=STATE_HALF_OPEN)
            self._circuits_by_endpoint[endpoint_id] = circuit

            return True

    def open(self, endpoint_id: str) -> ExecutionNetworkCircuit:
        """
        Force endpoint_id's circuit OPEN.

        Raises:
            ExecutionNetworkCircuitError: If endpoint_id is None or
                blank
        """

        self._validate_text(endpoint_id, "endpoint ID")

        with self._lock:
            circuit = self._resolve_or_create(endpoint_id)
            circuit = replace(circuit, state=STATE_OPEN, opened_at=datetime.now(timezone.utc))
            self._circuits_by_endpoint[endpoint_id] = circuit

            return circuit

    def close(self, endpoint_id: str) -> ExecutionNetworkCircuit:
        """
        Force endpoint_id's circuit CLOSED, resetting failure_count.

        Raises:
            ExecutionNetworkCircuitError: If endpoint_id is None or
                blank
        """

        self._validate_text(endpoint_id, "endpoint ID")

        with self._lock:
            circuit = self._resolve_or_create(endpoint_id)
            circuit = replace(circuit, failure_count=0, state=STATE_CLOSED, opened_at=None)
            self._circuits_by_endpoint[endpoint_id] = circuit

            return circuit

    def state(self, endpoint_id: str) -> str:
        """
        endpoint_id's currently stored circuit state, without
        evaluating recovery timing.

        Raises:
            ExecutionNetworkCircuitError: If endpoint_id is None or
                blank
        """

        self._validate_text(endpoint_id, "endpoint ID")

        with self._lock:
            return self._resolve_or_create(endpoint_id).state

    def _resolve_or_create(self, endpoint_id: str) -> ExecutionNetworkCircuit:
        circuit = self._circuits_by_endpoint.get(endpoint_id)

        if circuit is None:
            circuit = ExecutionNetworkCircuit(
                circuit_id=str(uuid4()),
                endpoint_id=endpoint_id,
                failure_count=0,
                threshold=self._failure_threshold,
                state=STATE_CLOSED,
                opened_at=None,
            )
            self._circuits_by_endpoint[endpoint_id] = circuit

        return circuit

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkCircuitError(f"Cannot use an empty or blank {field_name}.")
