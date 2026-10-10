from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_artifact_consumption_provenance_error import (
    ExecutionArtifactConsumptionProvenanceError,
)


@dataclass(frozen=True)
class ExecutionArtifactConsumptionProvenance:
    """
    Immutable record of a single consumption operation: which
    consumer, session, and exact artifact version participated in it.

    The record is a value object only. It performs no recording of
    its own; recording and looking up provenance is the
    responsibility of an execution artifact consumption provenance
    service.

    Attributes:
        provenance_id: The record's unique identifier
        consumption_id: The identifier of the consumption session the
            operation took place in
        artifact_id: The identifier of the consumed artifact
        version: The exact version of the artifact that was consumed
        consumer: Who performed the consumption operation
        recorded_at: When this record was captured
    """

    consumption_id: str

    artifact_id: str

    version: int

    consumer: str

    provenance_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    recorded_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.provenance_id, "provenance ID")
        self._require_text(self.consumption_id, "consumption ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.consumer, "consumer")

        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ExecutionArtifactConsumptionProvenanceError(
                "Cannot build an execution artifact consumption provenance record with a version below 1."
            )

        if not isinstance(self.recorded_at, datetime):
            raise ExecutionArtifactConsumptionProvenanceError(
                "Cannot build an execution artifact consumption provenance record with a non-datetime "
                "recorded_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionProvenanceError(
                f"Cannot build an execution artifact consumption provenance record with an empty or blank "
                f"{field_name}."
            )
