from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_artifact_consumption_error import (
    ExecutionArtifactConsumptionError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "ACTIVE",
        "FINISHED",
    }
)


@dataclass(frozen=True)
class ExecutionArtifactConsumptionSession:
    """
    Immutable snapshot of a consumer's ongoing consumption of a set
    of execution artifacts.

    The session is a value object only. It performs no permission
    checking or persistence of its own; starting a session, adding
    and removing artifacts, finishing it, and looking up active
    sessions is the responsibility of an execution artifact
    consumption service.

    Attributes:
        consumption_id: The session's unique identifier
        consumer: Who this session tracks consumption for
        artifact_ids: The distinct artifacts currently being
            consumed in this session, in the order they were added
        started_at: When this session was started
        status: The session's current status, one of ACTIVE or
            FINISHED
    """

    consumer: str

    artifact_ids: tuple

    consumption_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    status: str = "ACTIVE"

    def __post_init__(self):
        self._require_text(self.consumption_id, "consumption ID")
        self._require_text(self.consumer, "consumer")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionArtifactConsumptionError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if not isinstance(self.started_at, datetime):
            raise ExecutionArtifactConsumptionError(
                "Cannot build an execution artifact consumption session with a non-datetime started_at."
            )

        if self.artifact_ids is None:
            raise ExecutionArtifactConsumptionError(
                "Cannot build an execution artifact consumption session with a None artifact_ids."
            )

        artifact_id_list = list(self.artifact_ids)

        if not all(isinstance(artifact_id, str) and artifact_id.strip() for artifact_id in artifact_id_list):
            raise ExecutionArtifactConsumptionError(
                "Cannot build an execution artifact consumption session with a blank or non-string "
                "artifact ID."
            )

        normalized_ids = tuple(artifact_id_list)

        if len(set(normalized_ids)) != len(normalized_ids):
            raise ExecutionArtifactConsumptionError(
                "Cannot build an execution artifact consumption session with duplicate artifact IDs."
            )

        object.__setattr__(self, "artifact_ids", normalized_ids)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionError(
                f"Cannot build an execution artifact consumption session with an empty or blank {field_name}."
            )
