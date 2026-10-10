from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .execution_network_endpoint import (
    STATUS_ACTIVE,
)

from .execution_network_endpoint_health import (
    ExecutionNetworkEndpointHealth,
    STATUS_DEGRADED,
    STATUS_HEALTHY,
    STATUS_UNREACHABLE,
)

from .execution_network_endpoint_health_error import (
    ExecutionNetworkEndpointHealthError,
)

DEFAULT_DEGRADED_LATENCY_MS = 200.0


class ExecutionNetworkEndpointHealthService:
    """
    Continuously determines whether registered runtime endpoints are
    reachable and usable.

    Composes with:
        endpoint_service: get(endpoint_id) -> object with .status
            (ExecutionNetworkEndpointService)
        prober: measure(endpoint) -> latency_ms, raising an exception
            describing why when the endpoint could not be reached

    Behavior:
    - check() probes a fresh snapshot for endpoint_id, but only for
      an endpoint whose current registration status is ACTIVE; a
      prober failure produces an UNREACHABLE snapshot carrying the
      failure's message as failure_reason, a latency at or below
      DEFAULT_DEGRADED_LATENCY_MS produces a HEALTHY snapshot, and a
      higher latency produces a DEGRADED snapshot carrying a
      failure_reason describing the exceeded threshold; every
      snapshot is appended to that endpoint's history
    - healthy() derives from a fresh check()
    - unhealthy() re-checks every endpoint this service has ever
      checked and reports a fresh snapshot for each one that is not
      currently HEALTHY
    - history() reports every snapshot recorded for endpoint_id,
      oldest first

    The service never mutates endpoint configuration: it only ever
    reads from the composed endpoint service via get().

    The service is:
    - Thread-safe: All mutation and reads of its own history are
      guarded by an internal lock
    """

    def __init__(self, endpoint_service, prober, degraded_latency_ms: float = DEFAULT_DEGRADED_LATENCY_MS):
        self._endpoint_service = endpoint_service
        self._prober = prober
        self._degraded_latency_ms = degraded_latency_ms
        self._history_by_endpoint = {}
        self._lock = RLock()

    def check(self, endpoint_id: str) -> ExecutionNetworkEndpointHealth:
        """
        Probe a fresh health snapshot for endpoint_id.

        Raises:
            ExecutionNetworkEndpointHealthError: If endpoint_id is
                None or blank, endpoint_id is unknown, or the
                endpoint is not currently ACTIVE
        """

        self._validate_text(endpoint_id, "endpoint ID")

        endpoint = self._resolve_endpoint(endpoint_id)

        if endpoint.status != STATUS_ACTIVE:
            raise ExecutionNetworkEndpointHealthError(
                f"Cannot check health of endpoint ID {endpoint_id!r}: it is not active "
                f"(status is {endpoint.status!r})."
            )

        try:
            latency_ms = self._prober.measure(endpoint)
        except Exception as error:
            snapshot = ExecutionNetworkEndpointHealth(
                endpoint_id=endpoint_id,
                status=STATUS_UNREACHABLE,
                latency_ms=None,
                checked_at=datetime.now(timezone.utc),
                failure_reason=str(error),
            )
        else:
            if latency_ms > self._degraded_latency_ms:
                snapshot = ExecutionNetworkEndpointHealth(
                    endpoint_id=endpoint_id,
                    status=STATUS_DEGRADED,
                    latency_ms=latency_ms,
                    checked_at=datetime.now(timezone.utc),
                    failure_reason=(
                        f"latency {latency_ms}ms exceeds threshold {self._degraded_latency_ms}ms"
                    ),
                )
            else:
                snapshot = ExecutionNetworkEndpointHealth(
                    endpoint_id=endpoint_id,
                    status=STATUS_HEALTHY,
                    latency_ms=latency_ms,
                    checked_at=datetime.now(timezone.utc),
                    failure_reason=None,
                )

        with self._lock:
            self._history_by_endpoint.setdefault(endpoint_id, []).append(snapshot)

        return snapshot

    def healthy(self, endpoint_id: str) -> bool:
        """
        Whether endpoint_id is currently HEALTHY.
        """

        return self.check(endpoint_id).status == STATUS_HEALTHY

    def unhealthy(self) -> tuple:
        """
        A fresh health snapshot for every endpoint this service has
        ever checked that is not currently HEALTHY.
        """

        with self._lock:
            endpoint_ids = tuple(self._history_by_endpoint.keys())

        snapshots = []

        for endpoint_id in endpoint_ids:
            try:
                snapshot = self.check(endpoint_id)
            except ExecutionNetworkEndpointHealthError:
                continue

            if snapshot.status != STATUS_HEALTHY:
                snapshots.append(snapshot)

        return tuple(snapshots)

    def history(self, endpoint_id: str) -> tuple:
        """
        Every health snapshot recorded for endpoint_id, oldest first.

        Raises:
            ExecutionNetworkEndpointHealthError: If endpoint_id is
                None or blank, or no snapshot has been recorded for
                it
        """

        self._validate_text(endpoint_id, "endpoint ID")

        with self._lock:
            records = self._history_by_endpoint.get(endpoint_id)

            if not records:
                raise ExecutionNetworkEndpointHealthError(
                    f"No health snapshot is recorded for endpoint ID {endpoint_id!r}."
                )

            return tuple(records)

    def _resolve_endpoint(self, endpoint_id: str):
        try:
            return self._endpoint_service.get(endpoint_id)
        except Exception as error:
            raise ExecutionNetworkEndpointHealthError(
                f"Cannot resolve endpoint ID {endpoint_id!r}: it is unknown."
            ) from error

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkEndpointHealthError(f"Cannot use an empty or blank {field_name}.")
