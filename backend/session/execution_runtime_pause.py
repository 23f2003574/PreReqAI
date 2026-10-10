from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_runtime_pause_error import (
    ExecutionRuntimePauseError,
)


@dataclass(frozen=True)
class ExecutionRuntimePause:
    """
    Immutable record of a single pause of a running execution, from
    the moment it paused to the moment (if any) it resumed.

    The pause is a value object only. It performs no pause/resume
    accounting of its own; pausing and resuming is the responsibility
    of an execution runtime pause service, which produces a new
    record for every pause rather than mutating an existing one (a
    resume updates resumed_at on that same record via `replace`,
    since it completes the pause it belongs to).

    Attributes:
        pause_id: The pause's unique identifier
        runtime_id: The identifier of the runtime that was paused
        reason: Why the runtime was paused
        paused_at: When the runtime paused
        resumed_at: When the runtime resumed, or None if it is still
            paused
    """

    pause_id: str

    runtime_id: str

    reason: str

    paused_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    resumed_at: datetime = None

    def __post_init__(self):
        self._require_text(self.pause_id, "pause ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.reason, "reason")

        if self.paused_at is None or not isinstance(self.paused_at, datetime):
            raise ExecutionRuntimePauseError(
                "Cannot build an execution runtime pause with a non-datetime paused_at."
            )

        if self.resumed_at is not None and not isinstance(self.resumed_at, datetime):
            raise ExecutionRuntimePauseError(
                "Cannot build an execution runtime pause with a non-datetime resumed_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimePauseError(
                f"Cannot build an execution runtime pause with an empty or blank {field_name}."
            )
