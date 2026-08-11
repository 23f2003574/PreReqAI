from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_observation_health_error import (
    ExecutionObservationHealthError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "HEALTHY",
        "DEGRADED",
        "UNHEALTHY",
    }
)


@dataclass(frozen=True)
class ExecutionObservationHealth:
    """
    Immutable snapshot of a single health check, combining a
    session's metrics, traces, errors, and alerts into one overall
    status.

    The health record is a value object only. It performs no
    evaluation of its own; running a check, listing unhealthy or
    healthy sessions, and looking up a session's check history is
    the responsibility of an execution observation health service.

    Attributes:
        session_id: The identifier of the execution session this
            check covers
        status: The session's overall status at checked_at, one of
            HEALTHY, DEGRADED, or UNHEALTHY
        reasons: Why the session is DEGRADED or UNHEALTHY, in
            deterministic order; always empty when status is HEALTHY
        checked_at: When this check was performed
    """

    session_id: str

    status: str

    reasons: tuple = field(
        default_factory=tuple,
    )

    checked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.session_id, "session ID")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionObservationHealthError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if self.reasons is None:
            raise ExecutionObservationHealthError(
                "Cannot build an execution observation health record with a None reasons."
            )

        reason_list = list(self.reasons)

        for reason in reason_list:
            self._require_text(reason, "reason")

        object.__setattr__(self, "reasons", tuple(reason_list))

        if not isinstance(self.checked_at, datetime):
            raise ExecutionObservationHealthError(
                "Cannot build an execution observation health record with a non-datetime checked_at."
            )

        if self.status == "HEALTHY" and reason_list:
            raise ExecutionObservationHealthError(
                "Cannot build a HEALTHY execution observation health record with reasons."
            )

        if self.status != "HEALTHY" and not reason_list:
            raise ExecutionObservationHealthError(
                f"Cannot build a {self.status} execution observation health record without reasons."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationHealthError(
                f"Cannot build an execution observation health record with an empty or blank {field_name}."
            )
