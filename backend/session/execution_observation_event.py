from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import Any

from uuid import uuid4

from .execution_observation_event_error import (
    ExecutionObservationEventError,
)


@dataclass(frozen=True)
class ExecutionObservationEvent:
    """
    Immutable record of a single execution observation event, the
    foundation for observability into workspace execution sessions.

    The event is a value object only. It performs no recording of
    its own; recording, retrieving, and filtering events is the
    responsibility of an execution observation event service.

    Attributes:
        event_id: The event's unique identifier
        session_id: The identifier of the execution session the
            event occurred in
        event_type: What kind of event this is, e.g. "STARTED" or
            "COMPLETED"
        timestamp: When this event occurred
        metadata: Arbitrary additional details about the event
    """

    session_id: str

    event_type: str

    event_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    def __post_init__(self):
        self._require_text(self.event_id, "event ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.event_type, "event type")

        if not isinstance(self.timestamp, datetime):
            raise ExecutionObservationEventError(
                "Cannot build an execution observation event with a non-datetime timestamp."
            )

        if not isinstance(self.metadata, dict):
            raise ExecutionObservationEventError(
                "Cannot build an execution observation event with a non-dict metadata."
            )

        for key in self.metadata:
            self._require_text(key, "metadata key")

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationEventError(
                f"Cannot build an execution observation event with an empty or blank {field_name}."
            )
