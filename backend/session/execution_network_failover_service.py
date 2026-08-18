from threading import (
    RLock,
)

from uuid import uuid4

from .execution_network_failover import (
    ExecutionNetworkFailover,
    STATUS_FAILED,
    STATUS_FAILOVER,
    STATUS_PRIMARY,
)

from .execution_network_failover_error import (
    ExecutionNetworkFailoverError,
)


class ExecutionNetworkFailoverService:
    """
    Automatically reroutes runtime traffic when the selected endpoint
    becomes unavailable.

    Composes with:
        health_service: healthy(endpoint_id) -> bool
            (ExecutionNetworkEndpointHealthService)
        circuit_service: allow(endpoint_id) -> bool
            (ExecutionNetworkCircuitBreakerService)

    Behavior:
    - register() stores runtime_id's primary and backup endpoints and
      immediately performs a first selection
    - execute() re-runs selection against current health and circuit
      state and stores the result; it always succeeds, recording
      status FAILED with no selected_endpoint when every endpoint is
      unavailable rather than raising
    - select() runs the same deterministic selection (primary first,
      then backups in registration order, skipping any endpoint that
      is unhealthy or whose circuit is open) but is read-only and
      raises when no endpoint is currently available
    - status() reports the status of the most recently stored
      selection for runtime_id

    An endpoint is eligible only when it is both healthy and its
    circuit currently allows traffic; a failure evaluating either is
    treated as ineligible.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, health_service, circuit_service):
        self._health_service = health_service
        self._circuit_service = circuit_service
        self._configs_by_runtime = {}
        self._records_by_runtime = {}
        self._lock = RLock()

    def register(self, runtime_id: str, endpoints) -> ExecutionNetworkFailover:
        """
        Configure runtime_id's primary and backup endpoints, drawn
        from endpoints via "primary" and "backups" (item or attribute
        access, backups defaulting to empty), and perform an initial
        selection.

        Raises:
            ExecutionNetworkFailoverError: If runtime_id is None or
                blank, or the primary or any backup endpoint is None
                or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        primary = self._extract(endpoints, "primary")
        backups = tuple(self._extract(endpoints, "backups", ()) or ())

        self._validate_text(primary, "primary endpoint")

        for backup in backups:
            self._validate_text(backup, "backup endpoint")

        with self._lock:
            self._configs_by_runtime[runtime_id] = (primary, backups)

        return self._recompute(runtime_id)

    def execute(self, runtime_id: str) -> ExecutionNetworkFailover:
        """
        Re-run selection for runtime_id against current health and
        circuit state, storing and returning the result.

        Raises:
            ExecutionNetworkFailoverError: If runtime_id is None or
                blank, or no endpoints are registered for it
        """

        self._validate_text(runtime_id, "runtime ID")
        self._resolve_config(runtime_id)

        return self._recompute(runtime_id)

    def select(self, runtime_id: str) -> str:
        """
        The endpoint that is currently eligible for runtime_id:
        the primary if it is healthy and its circuit allows traffic,
        otherwise the first eligible backup in registration order.

        Raises:
            ExecutionNetworkFailoverError: If runtime_id is None or
                blank, no endpoints are registered for it, or every
                endpoint is currently unavailable
        """

        self._validate_text(runtime_id, "runtime ID")
        primary, backups = self._resolve_config(runtime_id)

        for candidate in (primary,) + backups:
            if self._is_eligible(candidate):
                return candidate

        raise ExecutionNetworkFailoverError(
            f"Cannot select an endpoint for runtime ID {runtime_id!r}: every endpoint is unavailable."
        )

    def status(self, runtime_id: str) -> str:
        """
        The status of the most recently stored selection for
        runtime_id.

        Raises:
            ExecutionNetworkFailoverError: If runtime_id is None or
                blank, or no selection has been recorded for it
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            record = self._records_by_runtime.get(runtime_id)

            if record is None:
                raise ExecutionNetworkFailoverError(
                    f"No failover selection is recorded for runtime ID {runtime_id!r}."
                )

            return record.status

    def _recompute(self, runtime_id: str) -> ExecutionNetworkFailover:
        primary, backups = self._resolve_config(runtime_id)

        selected_endpoint = None
        status = STATUS_FAILED

        for index, candidate in enumerate((primary,) + backups):
            if self._is_eligible(candidate):
                selected_endpoint = candidate
                status = STATUS_PRIMARY if index == 0 else STATUS_FAILOVER
                break

        record = ExecutionNetworkFailover(
            failover_id=str(uuid4()),
            runtime_id=runtime_id,
            primary_endpoint=primary,
            backup_endpoints=backups,
            selected_endpoint=selected_endpoint,
            status=status,
        )

        with self._lock:
            self._records_by_runtime[runtime_id] = record

        return record

    def _is_eligible(self, endpoint_id: str) -> bool:
        try:
            if not self._health_service.healthy(endpoint_id):
                return False
        except Exception:
            return False

        try:
            return bool(self._circuit_service.allow(endpoint_id))
        except Exception:
            return False

    def _resolve_config(self, runtime_id: str):
        config = self._configs_by_runtime.get(runtime_id)

        if config is None:
            raise ExecutionNetworkFailoverError(
                f"No endpoints are registered for runtime ID {runtime_id!r}."
            )

        return config

    @staticmethod
    def _extract(source, key: str, default=None):
        try:
            return source[key]
        except (TypeError, KeyError, IndexError):
            return getattr(source, key, default)

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkFailoverError(f"Cannot use an empty or blank {field_name}.")
