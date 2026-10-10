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

from .execution_observation_error_error import (
    ExecutionObservationErrorError,
)


@dataclass(frozen=True)
class ExecutionObservationError:
    """
    Immutable record of a single execution failure, kept queryable
    by session and stage for diagnosis.

    The error is a value object only. It performs no recording of
    its own; recording, retrieving, and filtering errors is the
    responsibility of an execution observation error service.

    Attributes:
        error_id: The error's unique identifier
        session_id: The identifier of the execution session the
            error occurred in
        stage_id: The identifier of the stage the error occurred in,
            or None if it is not associated with a specific stage
        error_type: What kind of error this is, e.g. "TIMEOUT" or
            "VALIDATION_FAILURE"
        message: The original error message, preserved verbatim
        timestamp: When this error occurred
        metadata: Arbitrary additional details about the error
    """

    session_id: str

    error_type: str

    message: str

    stage_id: str | None = None

    error_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    def __post_init__(self):
        self._require_text(self.error_id, "error ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.error_type, "error type")
        self._require_text(self.message, "message")

        if self.stage_id is not None:
            self._require_text(self.stage_id, "stage ID")

        if not isinstance(self.timestamp, datetime):
            raise ExecutionObservationErrorError(
                "Cannot build an execution observation error with a non-datetime timestamp."
            )

        if not isinstance(self.metadata, dict):
            raise ExecutionObservationErrorError(
                "Cannot build an execution observation error with a non-dict metadata."
            )

        for key in self.metadata:
            self._require_text(key, "metadata key")

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationErrorError(
                f"Cannot build an execution observation error with an empty or blank {field_name}."
            )
