from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_observation_health_transition_error import (
    ExecutionObservationHealthTransitionError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "HEALTHY",
        "DEGRADED",
        "UNHEALTHY",
    }
)


@dataclass(frozen=True)
class ExecutionObservationHealthTransition:
    """
    Immutable record of a session's health status changing from one
    value to another, kept so operators can see when and why a
    session's state changed.

    The transition is a value object only. It performs no recording
    of its own; recording, retrieving, and filtering transitions is
    the responsibility of an execution observation health history
    service.

    Attributes:
        transition_id: The transition's unique identifier
        session_id: The identifier of the execution session that
            transitioned
        previous_status: The session's status immediately before
            this transition
        current_status: The session's status immediately after this
            transition; always different from previous_status
        reasons: Why the session is now current_status, in the order
            given
        timestamp: When this transition occurred
    """

    session_id: str

    previous_status: str

    current_status: str

    reasons: tuple = field(
        default_factory=tuple,
    )

    transition_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.transition_id, "transition ID")
        self._require_text(self.session_id, "session ID")
        self._require_status(self.previous_status, "previous status")
        self._require_status(self.current_status, "current status")

        if self.previous_status == self.current_status:
            raise ExecutionObservationHealthTransitionError(
                "Cannot build an execution observation health transition with an unchanged status."
            )

        if self.reasons is None:
            raise ExecutionObservationHealthTransitionError(
                "Cannot build an execution observation health transition with a None reasons."
            )

        reason_list = list(self.reasons)

        for reason in reason_list:
            self._require_text(reason, "reason")

        object.__setattr__(self, "reasons", tuple(reason_list))

        if not isinstance(self.timestamp, datetime):
            raise ExecutionObservationHealthTransitionError(
                "Cannot build an execution observation health transition with a non-datetime timestamp."
            )

    def _require_status(self, value, field_name: str) -> None:
        self._require_text(value, field_name)

        if value not in SUPPORTED_STATUSES:
            raise ExecutionObservationHealthTransitionError(
                f"Unsupported {field_name} {value!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationHealthTransitionError(
                f"Cannot build an execution observation health transition with an empty or blank {field_name}."
            )
