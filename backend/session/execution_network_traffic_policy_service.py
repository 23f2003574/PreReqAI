from threading import (
    RLock,
)

from .execution_network_endpoint import (
    PROTOCOLS,
)

from .execution_network_traffic_policy import (
    DIRECTIONS,
    ExecutionNetworkTrafficPolicy,
)

from .execution_network_traffic_policy_error import (
    ExecutionNetworkTrafficPolicyError,
)


class ExecutionNetworkTrafficPolicyService:
    """
    Controls which runtime endpoints may accept or send network
    traffic.

    Behavior:
    - register() admits a policy that was already built by the
      caller, but only once per policy_id; a second register() for
      the same policy_id is rejected outright
    - evaluate() decides whether traffic matching runtime_id,
      endpoint_id, direction, and protocol is allowed: among enabled
      policies for that runtime and direction whose protocols include
      protocol, an endpoint-specific policy (matching endpoint_id)
      always overrides a runtime-wide default (endpoint_id is None);
      when several policies apply at the same specificity, the most
      recently registered one wins; with no matching policy at all,
      traffic is denied by default
    - disable() marks a policy ignored by evaluate() without removing
      or otherwise mutating it; disabling an already-disabled policy
      is a no-op
    - policies() reports every policy registered for a runtime, in
      registration order, including disabled ones

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._policies_by_id = {}
        self._order = []
        self._disabled_ids = set()
        self._lock = RLock()

    def register(self, policy: ExecutionNetworkTrafficPolicy) -> ExecutionNetworkTrafficPolicy:
        """
        Register a policy.

        Raises:
            ExecutionNetworkTrafficPolicyError: If policy is not an
                ExecutionNetworkTrafficPolicy, or its policy_id is
                already registered
        """

        if not isinstance(policy, ExecutionNetworkTrafficPolicy):
            raise ExecutionNetworkTrafficPolicyError(
                f"Cannot register a policy that is not an ExecutionNetworkTrafficPolicy: {policy!r}."
            )

        with self._lock:
            if policy.policy_id in self._policies_by_id:
                raise ExecutionNetworkTrafficPolicyError(
                    f"Cannot register policy ID {policy.policy_id!r}: it is already registered."
                )

            self._policies_by_id[policy.policy_id] = policy
            self._order.append(policy.policy_id)

            return policy

    def evaluate(self, runtime_id: str, endpoint_id: str, direction: str, protocol: str) -> bool:
        """
        Whether traffic matching runtime_id, endpoint_id, direction,
        and protocol is allowed.

        Raises:
            ExecutionNetworkTrafficPolicyError: If runtime_id or
                endpoint_id is None or blank, direction is not one of
                DIRECTIONS, or protocol is not one of PROTOCOLS
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(endpoint_id, "endpoint ID")
        self._validate_direction(direction)
        self._validate_protocol(protocol)

        with self._lock:
            matching = [
                policy
                for policy_id in self._order
                for policy in (self._policies_by_id[policy_id],)
                if policy_id not in self._disabled_ids
                and policy.runtime_id == runtime_id
                and policy.direction == direction
                and protocol in policy.protocols
            ]

            endpoint_specific = [policy for policy in matching if policy.endpoint_id == endpoint_id]

            if endpoint_specific:
                return endpoint_specific[-1].allowed

            runtime_wide = [policy for policy in matching if policy.endpoint_id is None]

            if runtime_wide:
                return runtime_wide[-1].allowed

            return False

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

    def disable(self, policy_id: str) -> ExecutionNetworkTrafficPolicy:
        """
        Disable a policy so evaluate() ignores it. A no-op if the
        policy is already disabled.

        Raises:
            ExecutionNetworkTrafficPolicyError: If policy_id is None
                or blank, or no policy is registered under it
        """

        self._validate_text(policy_id, "policy ID")

        with self._lock:
            policy = self._resolve(policy_id)
            self._disabled_ids.add(policy_id)

            return policy

    def _resolve(self, policy_id: str) -> ExecutionNetworkTrafficPolicy:
        policy = self._policies_by_id.get(policy_id)

        if policy is None:
            raise ExecutionNetworkTrafficPolicyError(
                f"No policy is registered under policy ID {policy_id!r}."
            )

        return policy

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkTrafficPolicyError(f"Cannot use an empty or blank {field_name}.")

    @staticmethod
    def _validate_direction(direction: str) -> None:
        if direction not in DIRECTIONS:
            raise ExecutionNetworkTrafficPolicyError(f"Cannot use an unknown direction: {direction!r}.")

    @staticmethod
    def _validate_protocol(protocol: str) -> None:
        if protocol not in PROTOCOLS:
            raise ExecutionNetworkTrafficPolicyError(f"Cannot use an unknown protocol: {protocol!r}.")
