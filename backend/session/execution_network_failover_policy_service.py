import math

from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_network_traffic_policy import (
    DIRECTIONS,
)

from .execution_network_circuit import (
    STATE_OPEN,
)

from .execution_network_failover_policy import (
    ExecutionNetworkFailoverPolicy,
    TRIGGER_CIRCUIT_OPEN,
    TRIGGER_LATENCY,
    TRIGGER_QUOTA_EXCEEDED,
    TRIGGER_UNHEALTHY,
)

from .execution_network_failover_policy_error import (
    ExecutionNetworkFailoverPolicyError,
)


class ExecutionNetworkFailoverPolicyService:
    """
    Defines when network traffic should fail over based on endpoint
    health, circuit state, quota, or latency.

    Composes with:
        endpoint_service: active(runtime_id) -> tuple of objects
            with .endpoint_id (ExecutionNetworkEndpointService)
        health_service: healthy(endpoint_id) -> bool;
            check(endpoint_id) -> object with .latency_ms
            (ExecutionNetworkEndpointHealthService)
        circuit_service: state(endpoint_id) -> str
            (ExecutionNetworkCircuitBreakerService)
        quota_service: available(runtime_id, direction) -> float
            (ExecutionNetworkQuotaService)

    Behavior:
    - register() admits a policy that was already built by the
      caller, but only once per policy_id
    - evaluate() measures, for every enabled policy registered under
      runtime_id, the signal its trigger names against that runtime's
      currently active endpoints, and reports the policies (in
      registration order) whose signal is at or above their
      threshold; disabled policies are skipped entirely; a failure
      reading any composed service is treated as the worse-case
      signal for that trigger, keeping evaluation deterministic for
      the same underlying state
    - policies() reports every policy registered for a runtime, in
      registration order, including disabled ones
    - disable() replaces a policy with an otherwise identical one
      that has enabled=False; disabling an already-disabled policy
      simply returns it unchanged

    Signals:
    - UNHEALTHY: the number of the runtime's active endpoints that
      are not currently healthy
    - CIRCUIT_OPEN: the number of the runtime's active endpoints
      whose circuit is currently OPEN
    - QUOTA_EXCEEDED: the number of directions (INGRESS, EGRESS)
      whose available quota for the runtime is at or below zero
    - LATENCY: the highest currently measured latency, in
      milliseconds, among the runtime's active endpoints (an
      unreachable endpoint counts as infinite)

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, endpoint_service, health_service, circuit_service, quota_service):
        self._endpoint_service = endpoint_service
        self._health_service = health_service
        self._circuit_service = circuit_service
        self._quota_service = quota_service
        self._policies_by_id = {}
        self._order = []
        self._lock = RLock()

    def register(self, policy: ExecutionNetworkFailoverPolicy) -> ExecutionNetworkFailoverPolicy:
        """
        Register a policy.

        Raises:
            ExecutionNetworkFailoverPolicyError: If policy is not an
                ExecutionNetworkFailoverPolicy, or its policy_id is
                already registered
        """

        if not isinstance(policy, ExecutionNetworkFailoverPolicy):
            raise ExecutionNetworkFailoverPolicyError(
                f"Cannot register a policy that is not an ExecutionNetworkFailoverPolicy: {policy!r}."
            )

        with self._lock:
            if policy.policy_id in self._policies_by_id:
                raise ExecutionNetworkFailoverPolicyError(
                    f"Cannot register policy ID {policy.policy_id!r}: it is already registered."
                )

            self._policies_by_id[policy.policy_id] = policy
            self._order.append(policy.policy_id)

            return policy

    def evaluate(self, runtime_id: str) -> tuple:
        """
        The enabled policies registered under runtime_id whose
        trigger's currently measured signal is at or above their
        threshold, in registration order.

        Raises:
            ExecutionNetworkFailoverPolicyError: If runtime_id is
                None or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            policies = tuple(
                self._policies_by_id[policy_id]
                for policy_id in self._order
                if self._policies_by_id[policy_id].runtime_id == runtime_id
                and self._policies_by_id[policy_id].enabled
            )

        endpoint_ids = self._active_endpoint_ids(runtime_id)

        return tuple(
            policy
            for policy in policies
            if self._signal(policy.trigger, runtime_id, endpoint_ids) >= policy.threshold
        )

    def policies(self, runtime_id: str) -> tuple:
        """
        Every policy registered for runtime_id, in registration
        order, including disabled ones.
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            return tuple(
                self._policies_by_id[policy_id]
                for policy_id in self._order
                if self._policies_by_id[policy_id].runtime_id == runtime_id
            )

    def disable(self, policy_id: str) -> ExecutionNetworkFailoverPolicy:
        """
        Disable a policy so evaluate() skips it. A no-op if the
        policy is already disabled.

        Raises:
            ExecutionNetworkFailoverPolicyError: If policy_id is None
                or blank, or no policy is registered under it
        """

        self._validate_text(policy_id, "policy ID")

        with self._lock:
            policy = self._resolve(policy_id)

            if not policy.enabled:
                return policy

            disabled = replace(policy, enabled=False)
            self._policies_by_id[policy_id] = disabled

            return disabled

    def _active_endpoint_ids(self, runtime_id: str) -> tuple:
        try:
            endpoints = self._endpoint_service.active(runtime_id)
        except Exception:
            return ()

        return tuple(endpoint.endpoint_id for endpoint in endpoints)

    def _signal(self, trigger: str, runtime_id: str, endpoint_ids: tuple) -> float:
        if trigger == TRIGGER_UNHEALTHY:
            return sum(1 for endpoint_id in endpoint_ids if not self._safe_healthy(endpoint_id))

        if trigger == TRIGGER_CIRCUIT_OPEN:
            return sum(1 for endpoint_id in endpoint_ids if self._safe_circuit_state(endpoint_id) == STATE_OPEN)

        if trigger == TRIGGER_QUOTA_EXCEEDED:
            return sum(
                1
                for direction in DIRECTIONS
                if self._safe_available(runtime_id, direction) <= 0
            )

        if trigger == TRIGGER_LATENCY:
            latencies = [self._safe_latency(endpoint_id) for endpoint_id in endpoint_ids]

            return max(latencies) if latencies else 0.0

        return 0.0

    def _safe_healthy(self, endpoint_id: str) -> bool:
        try:
            return bool(self._health_service.healthy(endpoint_id))
        except Exception:
            return False

    def _safe_circuit_state(self, endpoint_id: str) -> str:
        try:
            return self._circuit_service.state(endpoint_id)
        except Exception:
            return STATE_OPEN

    def _safe_available(self, runtime_id: str, direction: str) -> float:
        try:
            return float(self._quota_service.available(runtime_id, direction))
        except Exception:
            return math.inf

    def _safe_latency(self, endpoint_id: str) -> float:
        try:
            health = self._health_service.check(endpoint_id)
        except Exception:
            return math.inf

        return health.latency_ms if health.latency_ms is not None else math.inf

    def _resolve(self, policy_id: str) -> ExecutionNetworkFailoverPolicy:
        policy = self._policies_by_id.get(policy_id)

        if policy is None:
            raise ExecutionNetworkFailoverPolicyError(
                f"No policy is registered under policy ID {policy_id!r}."
            )

        return policy

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkFailoverPolicyError(f"Cannot use an empty or blank {field_name}.")
