from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_runtime_state_error import (
    ExecutionRuntimeStateError,
)

STATE_STARTING = "STARTING"

STATE_RUNNING = "RUNNING"

STATE_PAUSED = "PAUSED"

STATE_STOPPING = "STOPPING"

STATE_STOPPED = "STOPPED"

STATE_FAILED = "FAILED"

STATES = (
    STATE_STARTING,
    STATE_RUNNING,
    STATE_PAUSED,
    STATE_STOPPING,
    STATE_STOPPED,
    STATE_FAILED,
)

TERMINAL_STATES = (
    STATE_STOPPED,
    STATE_FAILED,
)


@dataclass(frozen=True)
class ExecutionRuntimeState:
    """
    Immutable record of the authoritative lifecycle state of a
    running execution at a point in time.

    The state is a value object only. It performs no transition
    logic of its own; enforcing valid transitions and preserving
    history is the responsibility of an execution runtime state
    service, which produces a new record for every transition rather
    than mutating an existing one.

    Attributes:
        runtime_id: The identifier of the runtime this state
            describes
        state: The runtime's lifecycle state, one of STATES
        reason: Why the runtime transitioned to this state
        updated_at: When the runtime transitioned to this state
    """

    runtime_id: str

    state: str

    reason: str

    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.reason, "reason")

        if self.state not in STATES:
            raise ExecutionRuntimeStateError(
                f"Cannot build an execution runtime state with an unknown state: {self.state!r}."
            )

        if self.updated_at is None or not isinstance(self.updated_at, datetime):
            raise ExecutionRuntimeStateError(
                "Cannot build an execution runtime state with a non-datetime updated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeStateError(
                f"Cannot build an execution runtime state with an empty or blank {field_name}."
            )
