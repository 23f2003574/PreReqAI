from dataclasses import (
    dataclass,
)

from .execution_artifact_distribution_policy_error import (
    ExecutionArtifactDistributionPolicyError,
)


@dataclass(frozen=True)
class ExecutionArtifactDistributionPolicy:
    """
    Immutable, reusable set of rules controlling which artifacts may
    be distributed and which delivery requirements apply.

    The policy is a value object only. It performs no validation of
    its own; registering policies, assigning them to channels, and
    validating artifacts against them is the responsibility of an
    execution artifact distribution policy service.

    Attributes:
        policy_id: The policy's unique identifier
        allowed_types: The non-empty set of artifact types this
            policy permits, e.g. {"log", "report"}
        require_encryption: Whether an artifact must be currently
            encrypted to pass validation
        require_signature: Whether an artifact must have a recorded
            signature to pass validation
        require_integrity: Whether an artifact must have a recorded
            integrity checksum to pass validation
    """

    policy_id: str

    allowed_types: frozenset

    require_encryption: bool = False

    require_signature: bool = False

    require_integrity: bool = False

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")

        if self.allowed_types is None:
            raise ExecutionArtifactDistributionPolicyError(
                "Cannot build a distribution policy with an empty or blank allowed_types."
            )

        allowed_types_list = list(self.allowed_types)

        if not allowed_types_list:
            raise ExecutionArtifactDistributionPolicyError(
                "Cannot build a distribution policy with an empty or blank allowed_types."
            )

        normalized_types = frozenset(
            artifact_type.strip() for artifact_type in allowed_types_list if isinstance(artifact_type, str)
        )

        if len(normalized_types) != len(allowed_types_list) or "" in normalized_types:
            raise ExecutionArtifactDistributionPolicyError(
                "Cannot build a distribution policy with a blank or non-string allowed type."
            )

        object.__setattr__(self, "allowed_types", normalized_types)

        for flag_name in ("require_encryption", "require_signature", "require_integrity"):
            if not isinstance(getattr(self, flag_name), bool):
                raise ExecutionArtifactDistributionPolicyError(
                    f"Cannot build a distribution policy with a non-bool {flag_name}."
                )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionPolicyError(
                f"Cannot build a distribution policy with an empty or blank {field_name}."
            )
