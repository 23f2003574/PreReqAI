from dataclasses import (
    dataclass,
    field as dataclass_field,
)

from uuid import uuid4

from .execution_recovery_conflict_policy_error import (
    ExecutionRecoveryConflictPolicyError,
)

SUPPORTED_RESOLUTIONS = frozenset(
    {
        "CHECKPOINT",
        "CURRENT",
        "REJECT",
    }
)


@dataclass(frozen=True)
class ExecutionRecoveryConflictPolicy:
    """
    Immutable, reusable rule for automatically resolving recovery
    conflicts on a given field.

    The policy is a value object only. It performs no matching or
    resolution of its own; registering a policy, applying the
    matching enabled one to a conflict, listing a field's policies,
    and disabling one is the responsibility of an execution recovery
    conflict policy service.

    Attributes:
        policy_id: The policy's unique identifier
        field: The conflict field this policy applies to
        resolution: How a matching conflict should be resolved, one
            of CHECKPOINT (keep the checkpoint's value), CURRENT
            (keep the current runtime value), or REJECT (refuse to
            auto-resolve; the conflict requires manual attention)
        enabled: Whether this policy is currently active; a disabled
            policy is never applied
    """

    field: str

    resolution: str

    enabled: bool = True

    policy_id: str = dataclass_field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.field, "field")
        self._require_text(self.resolution, "resolution")

        if self.resolution not in SUPPORTED_RESOLUTIONS:
            raise ExecutionRecoveryConflictPolicyError(
                f"Unsupported resolution {self.resolution!r}: expected one of {sorted(SUPPORTED_RESOLUTIONS)}."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionRecoveryConflictPolicyError(
                "Cannot build an execution recovery conflict policy with a non-bool enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryConflictPolicyError(
                f"Cannot build an execution recovery conflict policy with an empty or blank {field_name}."
            )
