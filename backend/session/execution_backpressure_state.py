from dataclasses import (
    dataclass,
)

from .execution_backpressure_error import (
    ExecutionBackpressureError,
)

STATUS_NORMAL = "NORMAL"

STATUS_SATURATED = "SATURATED"

STATUSES = (
    STATUS_NORMAL,
    STATUS_SATURATED,
)


@dataclass(frozen=True)
class ExecutionBackpressureState:
    """
    Immutable record of how much queued work a scope is currently
    carrying against the limit it may accept.

    The state is a value object only. It performs no capacity
    accounting of its own; configuring a limit and recording
    enqueues and dequeues against it is the responsibility of an
    execution backpressure service, which produces a new record for
    every update rather than mutating an existing one.

    Attributes:
        scope_id: The scope this state governs
        max_queue: The maximum number of jobs the scope may hold
            queued at once. Must be at least 1
        current_queue: How many jobs the scope currently holds queued
        status: The scope's current state, one of STATUSES;
            SATURATED exactly when current_queue >= max_queue
    """

    scope_id: str

    max_queue: int

    current_queue: int = 0

    status: str = STATUS_NORMAL

    def __post_init__(self):
        self._require_text(self.scope_id, "scope ID")

        if not isinstance(self.max_queue, int) or isinstance(self.max_queue, bool):
            raise ExecutionBackpressureError(
                "Cannot build an execution backpressure state with a non-int max_queue."
            )

        if self.max_queue < 1:
            raise ExecutionBackpressureError(
                "Cannot build an execution backpressure state with a max_queue below 1."
            )

        if not isinstance(self.current_queue, int) or isinstance(self.current_queue, bool):
            raise ExecutionBackpressureError(
                "Cannot build an execution backpressure state with a non-int current_queue."
            )

        if self.current_queue < 0:
            raise ExecutionBackpressureError(
                "Cannot build an execution backpressure state with a negative current_queue."
            )

        if self.current_queue > self.max_queue:
            raise ExecutionBackpressureError(
                "Cannot build an execution backpressure state where current_queue exceeds max_queue."
            )

        if self.status not in STATUSES:
            raise ExecutionBackpressureError(
                f"Cannot build an execution backpressure state with an unknown status: {self.status!r}."
            )

        is_saturated = self.current_queue >= self.max_queue

        if is_saturated and self.status != STATUS_SATURATED:
            raise ExecutionBackpressureError(
                "Cannot build an execution backpressure state: current_queue meets max_queue but status is not "
                "SATURATED."
            )

        if not is_saturated and self.status != STATUS_NORMAL:
            raise ExecutionBackpressureError(
                "Cannot build an execution backpressure state: status is SATURATED but current_queue is below "
                "max_queue."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionBackpressureError(
                f"Cannot build an execution backpressure state with an empty or blank {field_name}."
            )
