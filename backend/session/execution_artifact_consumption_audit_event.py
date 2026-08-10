from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_artifact_consumption_audit_error import (
    ExecutionArtifactConsumptionAuditError,
)


@dataclass(frozen=True)
class ExecutionArtifactConsumptionAuditEvent:
    """
    Immutable record of a single artifact consumption event, kept for
    debugging and compliance.

    The event is a value object only. It performs no recording of
    its own; recording, retrieving, and purging events is the
    responsibility of an execution artifact consumption audit
    service.

    Attributes:
        event_id: The event's unique identifier
        consumption_id: The identifier of the consumption session the
            event occurred in
        artifact_id: The identifier of the artifact involved
        version: The exact version of the artifact involved
        event_type: What kind of event this is, e.g. "CONSUMED" or
            "RELEASED"
        recorded_at: When this event occurred
    """

    consumption_id: str

    artifact_id: str

    version: int

    event_type: str

    event_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    recorded_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.event_id, "event ID")
        self._require_text(self.consumption_id, "consumption ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.event_type, "event type")

        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ExecutionArtifactConsumptionAuditError(
                "Cannot build an execution artifact consumption audit event with a version below 1."
            )

        if not isinstance(self.recorded_at, datetime):
            raise ExecutionArtifactConsumptionAuditError(
                "Cannot build an execution artifact consumption audit event with a non-datetime "
                "recorded_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionAuditError(
                f"Cannot build an execution artifact consumption audit event with an empty or blank "
                f"{field_name}."
            )
