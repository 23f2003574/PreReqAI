from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_change_validation_error import (
    ExecutionChangeValidationError,
)


@dataclass(frozen=True)
class ExecutionChangeValidation:
    """
    Immutable snapshot of whether a change request's proposed changes
    satisfied governance rules at a point in time.

    The validation is a value object only. It performs no rule
    checking of its own; running the rules against a change request's
    proposed changes and producing this record is the responsibility
    of an execution change validation service. Once produced, a
    validation is never edited: revalidating a change request
    produces a new record, never a mutation of an old one.

    Attributes:
        validation_id: The validation's unique identifier
        change_id: The identifier of the change request this
            validation was run against
        valid: Whether the change request had zero violations at
            checked_at
        violations: Every violation found, in a fixed order. Empty
            exactly when valid is True
        checked_at: When this validation was run
    """

    validation_id: str

    change_id: str

    valid: bool

    violations: tuple

    checked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.validation_id, "validation ID")
        self._require_text(self.change_id, "change ID")

        if not isinstance(self.valid, bool):
            raise ExecutionChangeValidationError(
                "Cannot build an execution change validation with a non-bool valid."
            )

        if self.violations is None:
            raise ExecutionChangeValidationError(
                "Cannot build an execution change validation with a None violations collection."
            )

        violations_list = list(self.violations)

        for violation in violations_list:
            if not isinstance(violation, str) or not violation.strip():
                raise ExecutionChangeValidationError(
                    "Cannot build an execution change validation with a blank violation."
                )

        object.__setattr__(self, "violations", tuple(violations_list))

        if self.valid and self.violations:
            raise ExecutionChangeValidationError(
                "Cannot build an execution change validation: valid is True but violations is not empty."
            )

        if not self.valid and not self.violations:
            raise ExecutionChangeValidationError(
                "Cannot build an execution change validation: valid is False but violations is empty."
            )

        if not isinstance(self.checked_at, datetime):
            raise ExecutionChangeValidationError(
                "Cannot build an execution change validation with a non-datetime checked_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionChangeValidationError(
                f"Cannot build an execution change validation with an empty or blank {field_name}."
            )
