from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_runtime_handoff_error import (
    ExecutionRuntimeHandoffError,
)

STATUS_PENDING = "PENDING"

STATUS_ACCEPTED = "ACCEPTED"

STATUS_REJECTED = "REJECTED"

STATUSES = (
    STATUS_PENDING,
    STATUS_ACCEPTED,
    STATUS_REJECTED,
)


@dataclass(frozen=True)
class ExecutionRuntimeHandoff:
    """
    Immutable record of an interrupted runtime being handed off to
    recovery infrastructure, with the checkpoint it should resume
    from.

    The handoff is a value object only. It performs no accept/reject
    accounting of its own; deciding a handoff is the responsibility
    of an execution runtime handoff service, which produces a new
    record for that decision rather than mutating an existing one.
    Once a handoff is ACCEPTED it is treated as immutable and is never
    replaced again.

    Attributes:
        handoff_id: The handoff's unique identifier
        runtime_id: The identifier of the interrupted runtime being
            handed off
        checkpoint_id: The identifier of the checkpoint recovery
            should resume from
        reason: Why the runtime is being handed off (or, once
            decided, why it was rejected)
        status: The handoff's current state, one of STATUSES
        created_at: When the handoff was created
    """

    handoff_id: str

    runtime_id: str

    checkpoint_id: str

    reason: str

    status: str = STATUS_PENDING

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.handoff_id, "handoff ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.checkpoint_id, "checkpoint ID")
        self._require_text(self.reason, "reason")

        if self.status not in STATUSES:
            raise ExecutionRuntimeHandoffError(
                f"Cannot build an execution runtime handoff with an unknown status: {self.status!r}."
            )

        if self.created_at is None or not isinstance(self.created_at, datetime):
            raise ExecutionRuntimeHandoffError(
                "Cannot build an execution runtime handoff with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeHandoffError(
                f"Cannot build an execution runtime handoff with an empty or blank {field_name}."
            )
