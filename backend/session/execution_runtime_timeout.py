from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from numbers import (
    Real,
)

from .execution_runtime_timeout_error import (
    ExecutionRuntimeTimeoutError,
)

STATUS_ARMED = "ARMED"

STATUS_TRIGGERED = "TRIGGERED"

STATUSES = (
    STATUS_ARMED,
    STATUS_TRIGGERED,
)


@dataclass(frozen=True)
class ExecutionRuntimeTimeout:
    """
    Immutable record of a runtime's configured execution duration
    limit, and whether it has fired.

    The timeout is a value object only. It performs no elapsed-time
    accounting of its own; configuring, checking, and triggering
    timeouts is the responsibility of an execution runtime timeout
    service, which produces a new record for every transition rather
    than mutating an existing one.

    Attributes:
        timeout_id: The timeout's unique identifier
        runtime_id: The identifier of the runtime this timeout guards
        limit_seconds: The maximum allowed execution duration, in
            seconds
        triggered_at: When the timeout fired, or None if it has not
        status: The timeout's current state, one of STATUSES
    """

    timeout_id: str

    runtime_id: str

    limit_seconds: float

    triggered_at: datetime = None

    status: str = STATUS_ARMED

    def __post_init__(self):
        self._require_text(self.timeout_id, "timeout ID")
        self._require_text(self.runtime_id, "runtime ID")

        if (
            self.limit_seconds is None
            or isinstance(self.limit_seconds, bool)
            or not isinstance(self.limit_seconds, Real)
            or self.limit_seconds <= 0
        ):
            raise ExecutionRuntimeTimeoutError(
                f"Cannot build an execution runtime timeout with a non-positive limit_seconds: "
                f"{self.limit_seconds!r}."
            )

        if self.triggered_at is not None and not isinstance(self.triggered_at, datetime):
            raise ExecutionRuntimeTimeoutError(
                "Cannot build an execution runtime timeout with a non-datetime triggered_at."
            )

        if self.status not in STATUSES:
            raise ExecutionRuntimeTimeoutError(
                f"Cannot build an execution runtime timeout with an unknown status: {self.status!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeTimeoutError(
                f"Cannot build an execution runtime timeout with an empty or blank {field_name}."
            )
