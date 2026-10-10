from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_secret_posture_error import (
    ExecutionSecretPostureError,
)

from .execution_secret_posture_level import (
    ExecutionSecretPostureLevel,
)


@dataclass(frozen=True)
class ExecutionSecretSecurityPosture:
    """
    Immutable snapshot of a secret's security standing at the moment
    it was evaluated.

    The posture is a value object only. It performs no evaluation of
    its own; computing a posture from a secret's access, trust,
    lease, rotation, and revocation state is the responsibility of an
    execution secret security posture service.

    Attributes:
        secret_id: The identifier of the secret this posture was
            computed for
        level: The secret's overall standing, drawn from
            ExecutionSecretPostureLevel
        violations: The specific issues found, in the fixed order
            they are checked. Empty when level is SECURE
        checked_at: When this posture was computed
    """

    secret_id: str

    level: ExecutionSecretPostureLevel

    violations: tuple

    checked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.secret_id, "secret ID")

        try:
            normalized_level = ExecutionSecretPostureLevel(self.level)
        except ValueError as error:
            raise ExecutionSecretPostureError(
                f"Cannot build an execution secret security posture with an invalid level: {error}"
            ) from error

        object.__setattr__(self, "level", normalized_level)

        if self.violations is None:
            raise ExecutionSecretPostureError(
                "Cannot build an execution secret security posture with a None violations."
            )

        violations_list = list(self.violations)

        if any(not isinstance(violation, str) or not violation.strip() for violation in violations_list):
            raise ExecutionSecretPostureError(
                "Cannot build an execution secret security posture with a blank or non-string violation."
            )

        object.__setattr__(self, "violations", tuple(violations_list))

        if normalized_level == ExecutionSecretPostureLevel.SECURE and violations_list:
            raise ExecutionSecretPostureError(
                "Cannot build an execution secret security posture that is SECURE but has violations."
            )

        if normalized_level != ExecutionSecretPostureLevel.SECURE and not violations_list:
            raise ExecutionSecretPostureError(
                f"Cannot build an execution secret security posture that is {normalized_level.value} but has "
                f"no violations."
            )

        if not isinstance(self.checked_at, datetime):
            raise ExecutionSecretPostureError(
                "Cannot build an execution secret security posture with a non-datetime checked_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretPostureError(
                f"Cannot build an execution secret security posture with an empty or blank {field_name}."
            )
