from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from .execution_scheduling_window_error import (
    ExecutionSchedulingWindowError,
)


@dataclass(frozen=True)
class ExecutionSchedulingWindow:
    """
    Immutable record of a time window during which queued jobs in a
    scope are eligible to start.

    The window is a value object only. It performs no eligibility
    evaluation of its own; creating windows and checking a scope's
    eligibility against them is the responsibility of an execution
    scheduling window service, which produces a new record for every
    update rather than mutating an existing one.

    Attributes:
        window_id: The window's unique identifier
        scope_id: The scope this window governs
        starts_at: When the window opens, inclusive
        ends_at: When the window closes, exclusive. Must be strictly
            after starts_at
        enabled: Whether the window is currently in effect. A
            disabled window is never active and is never returned by
            next()
    """

    window_id: str

    scope_id: str

    starts_at: datetime

    ends_at: datetime

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.window_id, "window ID")
        self._require_text(self.scope_id, "scope ID")

        if not isinstance(self.starts_at, datetime) or not isinstance(self.ends_at, datetime):
            raise ExecutionSchedulingWindowError(
                "Cannot build an execution scheduling window with a non-datetime starts_at or ends_at."
            )

        if self.starts_at >= self.ends_at:
            raise ExecutionSchedulingWindowError(
                "Cannot build an execution scheduling window where starts_at does not precede ends_at."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionSchedulingWindowError(
                "Cannot build an execution scheduling window with a non-bool enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSchedulingWindowError(
                f"Cannot build an execution scheduling window with an empty or blank {field_name}."
            )
