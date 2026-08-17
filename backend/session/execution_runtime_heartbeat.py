from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_runtime_heartbeat_error import (
    ExecutionRuntimeHeartbeatError,
)

STATUS_OK = "OK"

STATUSES = (STATUS_OK,)


@dataclass(frozen=True)
class ExecutionRuntimeHeartbeat:
    """
    Immutable record that a running execution reported liveness at a
    point in time.

    The heartbeat is a value object only. It performs no liveness
    tracking of its own; recording heartbeats and judging health is
    the responsibility of an execution runtime heartbeat service,
    which produces a new record for every signal rather than mutating
    an existing one.

    Attributes:
        heartbeat_id: The heartbeat's unique identifier
        runtime_id: The identifier of the runtime that reported
            liveness
        recorded_at: When the heartbeat was recorded
        status: The heartbeat's state, one of STATUSES
    """

    heartbeat_id: str

    runtime_id: str

    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    status: str = STATUS_OK

    def __post_init__(self):
        self._require_text(self.heartbeat_id, "heartbeat ID")
        self._require_text(self.runtime_id, "runtime ID")

        if self.recorded_at is None or not isinstance(self.recorded_at, datetime):
            raise ExecutionRuntimeHeartbeatError(
                "Cannot build an execution runtime heartbeat with a non-datetime recorded_at."
            )

        if self.status not in STATUSES:
            raise ExecutionRuntimeHeartbeatError(
                f"Cannot build an execution runtime heartbeat with an unknown status: {self.status!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeHeartbeatError(
                f"Cannot build an execution runtime heartbeat with an empty or blank {field_name}."
            )
