from dataclasses import (
    dataclass,
)

from numbers import (
    Real,
)

from .execution_network_failover_policy_error import (
    ExecutionNetworkFailoverPolicyError,
)

TRIGGER_UNHEALTHY = "UNHEALTHY"

TRIGGER_CIRCUIT_OPEN = "CIRCUIT_OPEN"

TRIGGER_QUOTA_EXCEEDED = "QUOTA_EXCEEDED"

TRIGGER_LATENCY = "LATENCY"

TRIGGERS = (
    TRIGGER_UNHEALTHY,
    TRIGGER_CIRCUIT_OPEN,
    TRIGGER_QUOTA_EXCEEDED,
    TRIGGER_LATENCY,
)


@dataclass(frozen=True)
class ExecutionNetworkFailoverPolicy:
    """
    Immutable rule defining when a runtime's traffic should fail over,
    based on one measured signal crossing a threshold.

    The policy is a value object only. It performs no evaluation of
    its own; measuring the signal a trigger names and comparing it
    against threshold is the responsibility of an execution network
    failover policy service, which never mutates a registered policy
    (disabling one produces a new record rather than mutating the
    existing one).

    Attributes:
        policy_id: The policy's unique identifier
        runtime_id: The identifier of the runtime this policy governs
        trigger: Which signal this policy watches, one of TRIGGERS
        threshold: The value trigger's measured signal must reach or
            exceed for this policy to fire
        enabled: Whether this policy is currently evaluated
    """

    policy_id: str

    runtime_id: str

    trigger: str

    threshold: float

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.runtime_id, "runtime ID")

        if self.trigger not in TRIGGERS:
            raise ExecutionNetworkFailoverPolicyError(
                f"Cannot build an execution network failover policy with an unknown trigger: "
                f"{self.trigger!r}."
            )

        if (
            self.threshold is None
            or isinstance(self.threshold, bool)
            or not isinstance(self.threshold, Real)
            or self.threshold < 0
        ):
            raise ExecutionNetworkFailoverPolicyError(
                f"Cannot build an execution network failover policy with a negative threshold: "
                f"{self.threshold!r}."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionNetworkFailoverPolicyError(
                f"Cannot build an execution network failover policy with a non-boolean enabled: "
                f"{self.enabled!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkFailoverPolicyError(
                f"Cannot build an execution network failover policy with an empty or blank {field_name}."
            )
