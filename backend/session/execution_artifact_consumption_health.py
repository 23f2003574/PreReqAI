from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from .execution_artifact_consumption_health_error import (
    ExecutionArtifactConsumptionHealthError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "HEALTHY",
        "STALE",
        "UNHEALTHY",
    }
)


@dataclass(frozen=True)
class ExecutionArtifactConsumptionHealth:
    """
    Immutable snapshot of a consumption session's health at a single
    point in time.

    The health record is a value object only. It performs no
    checking of its own; combining lease, validation, and activity
    state into a health record is the responsibility of an execution
    artifact consumption health service.

    Attributes:
        consumption_id: The identifier of the checked consumption
            session
        status: The session's overall health, one of HEALTHY, STALE,
            or UNHEALTHY
        last_activity: When this session was last known to be active
        invalid_artifacts: The artifacts currently tracked by the
            session that failed validation or whose lease has expired
    """

    consumption_id: str

    status: str

    last_activity: datetime

    invalid_artifacts: tuple

    def __post_init__(self):
        self._require_text(self.consumption_id, "consumption ID")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionArtifactConsumptionHealthError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if not isinstance(self.last_activity, datetime):
            raise ExecutionArtifactConsumptionHealthError(
                "Cannot build an execution artifact consumption health record with a non-datetime "
                "last_activity."
            )

        if self.invalid_artifacts is None:
            raise ExecutionArtifactConsumptionHealthError(
                "Cannot build an execution artifact consumption health record with a None "
                "invalid_artifacts."
            )

        invalid_artifacts = tuple(self.invalid_artifacts)

        if not all(isinstance(artifact_id, str) and artifact_id.strip() for artifact_id in invalid_artifacts):
            raise ExecutionArtifactConsumptionHealthError(
                "Cannot build an execution artifact consumption health record with a blank or non-string "
                "artifact ID in invalid_artifacts."
            )

        object.__setattr__(self, "invalid_artifacts", invalid_artifacts)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionHealthError(
                f"Cannot build an execution artifact consumption health record with an empty or blank "
                f"{field_name}."
            )
