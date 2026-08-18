from dataclasses import (
    dataclass,
)

from .execution_network_endpoint import (
    PROTOCOLS,
)

from .execution_network_traffic_policy_error import (
    ExecutionNetworkTrafficPolicyError,
)

DIRECTION_INGRESS = "INGRESS"

DIRECTION_EGRESS = "EGRESS"

DIRECTIONS = (
    DIRECTION_INGRESS,
    DIRECTION_EGRESS,
)


@dataclass(frozen=True)
class ExecutionNetworkTrafficPolicy:
    """
    Immutable rule controlling whether traffic in a given direction
    and protocol may cross a runtime's (or one of its endpoint's)
    network boundary.

    The policy is a value object only. It performs no evaluation of
    its own; deciding which policy applies to a given piece of
    traffic is the responsibility of an execution network traffic
    policy service, which never mutates a registered policy.

    Attributes:
        policy_id: The policy's unique identifier
        runtime_id: The identifier of the runtime this policy governs
        direction: Which way the traffic flows, one of DIRECTIONS
        protocols: The protocols this policy applies to (each one of
            PROTOCOLS)
        allowed: Whether matching traffic is permitted
        endpoint_id: When set, restricts this policy to a single
            endpoint, taking precedence over any runtime-wide default;
            None means the policy applies to the whole runtime
    """

    policy_id: str

    runtime_id: str

    direction: str

    protocols: tuple

    allowed: bool

    endpoint_id: str = None

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.runtime_id, "runtime ID")

        if self.endpoint_id is not None:
            self._require_text(self.endpoint_id, "endpoint ID")

        if self.direction not in DIRECTIONS:
            raise ExecutionNetworkTrafficPolicyError(
                f"Cannot build an execution network traffic policy with an unknown direction: "
                f"{self.direction!r}."
            )

        if (
            self.protocols is None
            or not isinstance(self.protocols, tuple)
            or not self.protocols
            or any(protocol not in PROTOCOLS for protocol in self.protocols)
        ):
            raise ExecutionNetworkTrafficPolicyError(
                f"Cannot build an execution network traffic policy with invalid protocols: "
                f"{self.protocols!r}."
            )

        if not isinstance(self.allowed, bool):
            raise ExecutionNetworkTrafficPolicyError(
                f"Cannot build an execution network traffic policy with a non-boolean allowed: "
                f"{self.allowed!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkTrafficPolicyError(
                f"Cannot build an execution network traffic policy with an empty or blank {field_name}."
            )
