from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_recovery_validation_error import (
    ExecutionRecoveryValidationError,
)


@dataclass(frozen=True)
class ExecutionRecoveryValidation:
    """
    Immutable outcome of checking a recovery checkpoint against the
    rules that must hold before it can be restored from.

    The validation is a value object only. It performs no checking
    of its own; inspecting a checkpoint's session, stage, and
    completeness, and deciding which violations (if any) apply, is
    the responsibility of an execution recovery validation service.

    Attributes:
        checkpoint_id: The identifier of the checkpoint that was
            checked
        valid: Whether the checkpoint passed every check, i.e.
            violations is empty
        violations: The distinct, deterministically ordered reasons
            the checkpoint failed validation; empty when valid
        checked_at: When this validation was performed
    """

    checkpoint_id: str

    valid: bool

    violations: tuple = field(
        default_factory=tuple,
    )

    checked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.checkpoint_id, "checkpoint ID")

        if not isinstance(self.valid, bool):
            raise ExecutionRecoveryValidationError(
                "Cannot build an execution recovery validation with a non-bool valid."
            )

        if not isinstance(self.checked_at, datetime):
            raise ExecutionRecoveryValidationError(
                "Cannot build an execution recovery validation with a non-datetime checked_at."
            )

        if self.violations is None:
            raise ExecutionRecoveryValidationError(
                "Cannot build an execution recovery validation with a None violations."
            )

        violation_list = list(self.violations)

        for violation in violation_list:
            self._require_text(violation, "violation")

        object.__setattr__(self, "violations", tuple(violation_list))

        if self.valid:
            if self.violations:
                raise ExecutionRecoveryValidationError(
                    "Cannot build an execution recovery validation that is valid with violations present."
                )
        else:
            if not self.violations:
                raise ExecutionRecoveryValidationError(
                    "Cannot build an execution recovery validation that is invalid with no violations recorded."
                )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryValidationError(
                f"Cannot build an execution recovery validation with an empty or blank {field_name}."
            )
