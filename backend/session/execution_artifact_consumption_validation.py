from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_artifact_consumption_validation_error import (
    ExecutionArtifactConsumptionValidationError,
)


@dataclass(frozen=True)
class ExecutionArtifactConsumptionValidation:
    """
    Immutable outcome of checking whether a single artifact tracked
    by a consumption session still exists, is accessible to the
    session's consumer, and satisfies its required version.

    The validation is a value object only. It performs no checking of
    its own; running and reporting checks is the responsibility of an
    execution artifact consumption validation service.

    Attributes:
        consumption_id: The identifier of the consumption session the
            checked artifact belongs to
        artifact_id: The identifier of the checked artifact
        valid: Whether the artifact passed every check
        reason: A human-readable explanation of the outcome
        checked_at: When this check was performed
    """

    consumption_id: str

    artifact_id: str

    valid: bool

    reason: str

    checked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.consumption_id, "consumption ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.reason, "reason")

        if not isinstance(self.valid, bool):
            raise ExecutionArtifactConsumptionValidationError(
                "Cannot build an execution artifact consumption validation with a non-boolean valid."
            )

        if not isinstance(self.checked_at, datetime):
            raise ExecutionArtifactConsumptionValidationError(
                "Cannot build an execution artifact consumption validation with a non-datetime checked_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionValidationError(
                f"Cannot build an execution artifact consumption validation with an empty or blank "
                f"{field_name}."
            )
