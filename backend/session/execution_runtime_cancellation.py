from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_runtime_cancellation_error import (
    ExecutionRuntimeCancellationError,
)


@dataclass(frozen=True)
class ExecutionRuntimeCancellation:
    """
    Immutable record of a single cancellation of a runtime, from the
    moment it was requested to the moment (if any) it completed.

    The cancellation is a value object only. It performs no
    request/completion accounting of its own; requesting and
    completing cancellation is the responsibility of an execution
    runtime cancellation service, which mutates completed_at on this
    same record via `replace` once cancellation finishes, rather than
    producing an unrelated new record.

    Attributes:
        cancellation_id: The cancellation's unique identifier
        runtime_id: The identifier of the runtime being cancelled
        reason: Why the runtime is being cancelled
        requested_at: When cancellation was requested
        completed_at: When cancellation completed, or None if it is
            still in progress
    """

    cancellation_id: str

    runtime_id: str

    reason: str

    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    completed_at: datetime = None

    def __post_init__(self):
        self._require_text(self.cancellation_id, "cancellation ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.reason, "reason")

        if self.requested_at is None or not isinstance(self.requested_at, datetime):
            raise ExecutionRuntimeCancellationError(
                "Cannot build an execution runtime cancellation with a non-datetime requested_at."
            )

        if self.completed_at is not None and not isinstance(self.completed_at, datetime):
            raise ExecutionRuntimeCancellationError(
                "Cannot build an execution runtime cancellation with a non-datetime completed_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeCancellationError(
                f"Cannot build an execution runtime cancellation with an empty or blank {field_name}."
            )
