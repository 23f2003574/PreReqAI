from dataclasses import (
    dataclass,
    field,
)

from uuid import uuid4

from .execution_observation_escalation_policy_error import (
    ExecutionObservationEscalationPolicyError,
)


@dataclass(frozen=True)
class ExecutionObservationEscalationPolicy:
    """
    Immutable configuration describing when an incident of a given
    severity should be automatically escalated.

    The policy is a value object only. It performs no evaluation of
    its own; registering a policy and evaluating it against an
    incident is the responsibility of an execution observation
    incident escalation service.

    Attributes:
        policy_id: The policy's unique identifier
        severity: Which incident severity this policy applies to
        timeout_seconds: How long an incident of that severity may
            stay unescalated before this policy considers it in
            breach
        enabled: Whether this policy is evaluated at all; a disabled
            policy never triggers an escalation
    """

    severity: str

    timeout_seconds: float

    enabled: bool = True

    policy_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.severity, "severity")

        if not isinstance(self.enabled, bool):
            raise ExecutionObservationEscalationPolicyError(
                "Cannot build an execution observation escalation policy with a non-bool enabled."
            )

        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or self.timeout_seconds < 0
        ):
            raise ExecutionObservationEscalationPolicyError(
                "Cannot build an execution observation escalation policy with a negative or non-numeric "
                "timeout_seconds."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationEscalationPolicyError(
                f"Cannot build an execution observation escalation policy with an empty or blank {field_name}."
            )
