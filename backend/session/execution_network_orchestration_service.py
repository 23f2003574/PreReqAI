import math

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_network_traffic_policy import (
    DIRECTION_EGRESS,
)

from .execution_network_decision import (
    ExecutionNetworkDecision,
)

from .execution_network_decision_error import (
    ExecutionNetworkDecisionError,
)

DEFAULT_AMOUNT = 1.0


class ExecutionNetworkOrchestrationService:
    """
    Unifies endpoint health, routing, connections, policies, quotas,
    shaping, circuits, and failover into one network decision
    pipeline.

    Composes with (all duck-typed to the services already built in
    this package):
        endpoint_service: get(endpoint_id) -> object with .protocol
            (ExecutionNetworkEndpointService)
        health_service: healthy(endpoint_id) -> bool
            (ExecutionNetworkEndpointHealthService)
        circuit_service: allow(endpoint_id) -> bool
            (ExecutionNetworkCircuitBreakerService)
        traffic_policy_service: evaluate(runtime_id, endpoint_id,
            direction, protocol) -> bool
            (ExecutionNetworkTrafficPolicyService)
        connection_limit_service: can_open(runtime_id) -> bool;
            acquire(runtime_id, connection_id);
            release(runtime_id, connection_id)
            (ExecutionNetworkConnectionLimitService)
        connection_service: open(runtime_id, endpoint_id) -> object
            with .connection_id; close(connection_id);
            cleanup(runtime_id) -> tuple of such objects
            (ExecutionNetworkConnectionService)
        quota_service: available(runtime_id, direction) -> float;
            consume(runtime_id, direction, amount)
            (ExecutionNetworkQuotaService)
        shaping_service: remaining(runtime_id, direction) -> float;
            allow(runtime_id, direction, amount) -> bool
            (ExecutionNetworkTrafficShapingService)
        failover_service: select(runtime_id) -> endpoint_id;
            execute(runtime_id) -> object with .selected_endpoint
            (ExecutionNetworkFailoverService)
        failover_policy_service: evaluate(runtime_id) -> tuple
            (ExecutionNetworkFailoverPolicyService)

    Behavior:
    - connect() resolves the currently best endpoint via
      failover_service.select(), re-resolving through execute() if
      any registered failover policy is currently triggered, then
      runs the full pipeline against it: traffic policy, endpoint
      health and circuit state, connection limits, and quota/shaping,
      in that order; the first failing check determines the
      decision's reason and no endpoint is contacted; when every
      check passes, a connection is actually opened and counted
      against the connection limit, and quota/shaping capacity is
      consumed
    - evaluate() runs the same pipeline against a caller-specified
      endpoint_id, without opening a connection or consuming any
      capacity
    - reroute() disconnects any connections currently held by
      runtime_id, forces a fresh failover selection via
      failover_service.execute(), and runs the pipeline against the
      result exactly as connect() does
    - disconnect() closes every connection currently held by
      runtime_id and releases its connection-limit slots
    - decision() reports the most recently recorded decision for a
      runtime

    Every check reads the same way for the same underlying state, so
    a decision is deterministic; the outcome of every connect,
    evaluate, reroute, or disconnect call is recorded as this
    runtime's current decision.

    A resource that is simply not configured (no connection limit, no
    quota, no shaper, no failover policies) is treated as
    unrestricted rather than as a denial; a check that is configured
    but fails, or a health/circuit signal that cannot be read, is
    treated as a denial.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        endpoint_service,
        health_service,
        circuit_service,
        traffic_policy_service,
        connection_limit_service,
        connection_service,
        quota_service,
        shaping_service,
        failover_service,
        failover_policy_service,
    ):
        self._endpoint_service = endpoint_service
        self._health_service = health_service
        self._circuit_service = circuit_service
        self._traffic_policy_service = traffic_policy_service
        self._connection_limit_service = connection_limit_service
        self._connection_service = connection_service
        self._quota_service = quota_service
        self._shaping_service = shaping_service
        self._failover_service = failover_service
        self._failover_policy_service = failover_policy_service
        self._decisions_by_runtime = {}
        self._lock = RLock()

    def connect(self, runtime_id: str) -> ExecutionNetworkDecision:
        """
        Run the full pipeline for runtime_id against the currently
        best endpoint, opening a connection when every check passes.

        Raises:
            ExecutionNetworkDecisionError: If runtime_id is None or
                blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            try:
                endpoint_id = self._failover_service.select(runtime_id)
            except Exception:
                return self._store_decision(runtime_id, None, False, "no endpoint available")

            if self._safe_failover_triggered(runtime_id):
                endpoint_id = self._reselect(runtime_id, endpoint_id)

            return self._activate(runtime_id, endpoint_id)

    def evaluate(self, runtime_id: str, endpoint_id: str) -> ExecutionNetworkDecision:
        """
        Run the full pipeline for runtime_id against endpoint_id,
        without opening a connection or consuming any capacity.

        Raises:
            ExecutionNetworkDecisionError: If runtime_id or
                endpoint_id is None or blank
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(endpoint_id, "endpoint ID")

        with self._lock:
            allowed, reason = self._check(runtime_id, endpoint_id)

            return self._store_decision(runtime_id, endpoint_id, allowed, reason)

    def reroute(self, runtime_id: str) -> ExecutionNetworkDecision:
        """
        Disconnect runtime_id's current connections, force a fresh
        failover selection, and run the full pipeline against the
        result.

        Raises:
            ExecutionNetworkDecisionError: If runtime_id is None or
                blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            self._disconnect_locked(runtime_id)

            try:
                record = self._failover_service.execute(runtime_id)
            except Exception:
                return self._store_decision(runtime_id, None, False, "no endpoint available")

            if record.selected_endpoint is None:
                return self._store_decision(runtime_id, None, False, "no endpoint available")

            return self._activate(runtime_id, record.selected_endpoint)

    def disconnect(self, runtime_id: str) -> ExecutionNetworkDecision:
        """
        Close every connection currently held by runtime_id and
        release its connection-limit slots.

        Raises:
            ExecutionNetworkDecisionError: If runtime_id is None or
                blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            self._disconnect_locked(runtime_id)

            return self._store_decision(runtime_id, None, False, "disconnected")

    def decision(self, runtime_id: str) -> ExecutionNetworkDecision:
        """
        The most recently recorded decision for runtime_id.

        Raises:
            ExecutionNetworkDecisionError: If runtime_id is None or
                blank, or no decision has been recorded for it
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            record = self._decisions_by_runtime.get(runtime_id)

            if record is None:
                raise ExecutionNetworkDecisionError(
                    f"No decision is recorded for runtime ID {runtime_id!r}."
                )

            return record

    def _activate(self, runtime_id: str, endpoint_id: str) -> ExecutionNetworkDecision:
        allowed, reason = self._check(runtime_id, endpoint_id)

        if not allowed:
            return self._store_decision(runtime_id, endpoint_id, False, reason)

        try:
            connection = self._connection_service.open(runtime_id, endpoint_id)
        except Exception as error:
            return self._store_decision(
                runtime_id, endpoint_id, False, f"connection open failed: {error}"
            )

        try:
            self._connection_limit_service.acquire(runtime_id, connection.connection_id)
        except Exception:
            self._safe_close(connection.connection_id)

            return self._store_decision(runtime_id, endpoint_id, False, "connection limit exceeded")

        self._safe_consume(runtime_id)
        self._safe_shape(runtime_id)

        return self._store_decision(runtime_id, endpoint_id, True, "connected")

    def _check(self, runtime_id: str, endpoint_id: str) -> tuple:
        try:
            protocol = self._endpoint_service.get(endpoint_id).protocol
        except Exception:
            return False, "unknown endpoint"

        try:
            policy_allowed = self._traffic_policy_service.evaluate(
                runtime_id, endpoint_id, DIRECTION_EGRESS, protocol
            )
        except Exception:
            policy_allowed = False

        if not policy_allowed:
            return False, "traffic policy denied"

        if not self._safe_healthy(endpoint_id):
            return False, "endpoint unhealthy"

        if not self._safe_circuit_allow(endpoint_id):
            return False, "circuit open"

        if not self._safe_can_open(runtime_id):
            return False, "connection limit exceeded"

        if self._safe_available(runtime_id) <= 0:
            return False, "quota exceeded"

        if self._safe_remaining(runtime_id) < DEFAULT_AMOUNT:
            return False, "rate limited"

        return True, "allowed"

    def _reselect(self, runtime_id: str, fallback_endpoint_id: str) -> str:
        try:
            record = self._failover_service.execute(runtime_id)
        except Exception:
            return fallback_endpoint_id

        return record.selected_endpoint if record.selected_endpoint is not None else fallback_endpoint_id

    def _disconnect_locked(self, runtime_id: str) -> None:
        try:
            closed_connections = self._connection_service.cleanup(runtime_id)
        except Exception:
            closed_connections = ()

        for connection in closed_connections:
            try:
                self._connection_limit_service.release(runtime_id, connection.connection_id)
            except Exception:
                pass

    def _store_decision(
        self, runtime_id: str, endpoint_id: str, allowed: bool, reason: str
    ) -> ExecutionNetworkDecision:
        record = ExecutionNetworkDecision(
            decision_id=str(uuid4()),
            runtime_id=runtime_id,
            endpoint_id=endpoint_id,
            allowed=allowed,
            reason=reason,
            created_at=datetime.now(timezone.utc),
        )

        self._decisions_by_runtime[runtime_id] = record

        return record

    def _safe_healthy(self, endpoint_id: str) -> bool:
        try:
            return bool(self._health_service.healthy(endpoint_id))
        except Exception:
            return False

    def _safe_circuit_allow(self, endpoint_id: str) -> bool:
        try:
            return bool(self._circuit_service.allow(endpoint_id))
        except Exception:
            return False

    def _safe_can_open(self, runtime_id: str) -> bool:
        try:
            return bool(self._connection_limit_service.can_open(runtime_id))
        except Exception:
            return True

    def _safe_available(self, runtime_id: str) -> float:
        try:
            return float(self._quota_service.available(runtime_id, DIRECTION_EGRESS))
        except Exception:
            return math.inf

    def _safe_remaining(self, runtime_id: str) -> float:
        try:
            return float(self._shaping_service.remaining(runtime_id, DIRECTION_EGRESS))
        except Exception:
            return math.inf

    def _safe_consume(self, runtime_id: str) -> None:
        try:
            self._quota_service.consume(runtime_id, DIRECTION_EGRESS, DEFAULT_AMOUNT)
        except Exception:
            pass

    def _safe_shape(self, runtime_id: str) -> None:
        try:
            self._shaping_service.allow(runtime_id, DIRECTION_EGRESS, DEFAULT_AMOUNT)
        except Exception:
            pass

    def _safe_close(self, connection_id: str) -> None:
        try:
            self._connection_service.close(connection_id)
        except Exception:
            pass

    def _safe_failover_triggered(self, runtime_id: str) -> bool:
        try:
            return bool(self._failover_policy_service.evaluate(runtime_id))
        except Exception:
            return False

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkDecisionError(f"Cannot use an empty or blank {field_name}.")
