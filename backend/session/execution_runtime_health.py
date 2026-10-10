from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_runtime_health_error import (
    ExecutionRuntimeHealthError,
)

STATUS_HEALTHY = "HEALTHY"

STATUS_DEGRADED = "DEGRADED"

STATUS_FAILED = "FAILED"

STATUSES = (
    STATUS_HEALTHY,
    STATUS_DEGRADED,
    STATUS_FAILED,
)


@dataclass(frozen=True)
class ExecutionRuntimeHealth:
    """
    Immutable snapshot combining a runtime's heartbeat, timeout,
    resource, and lifecycle signals into a single health verdict at a
    point in time.

    The health snapshot is a value object only. It performs no signal
    gathering of its own; computing it from the underlying signals is
    the responsibility of an execution runtime health service, which
    produces a new snapshot for every check rather than mutating an
    existing one.

    Attributes:
        runtime_id: The identifier of the runtime this snapshot
            describes
        status: The combined health verdict, one of STATUSES
        issues: The specific problems found, in priority order (empty
            if none)
        checked_at: When this snapshot was computed
    """

    runtime_id: str

    status: str

    issues: tuple = ()

    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.runtime_id, "runtime ID")

        if self.status not in STATUSES:
            raise ExecutionRuntimeHealthError(
                f"Cannot build an execution runtime health snapshot with an unknown status: {self.status!r}."
            )

        if self.issues is None or not isinstance(self.issues, tuple):
            raise ExecutionRuntimeHealthError(
                "Cannot build an execution runtime health snapshot with a non-tuple issues."
            )

        if self.checked_at is None or not isinstance(self.checked_at, datetime):
            raise ExecutionRuntimeHealthError(
                "Cannot build an execution runtime health snapshot with a non-datetime checked_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeHealthError(
                f"Cannot build an execution runtime health snapshot with an empty or blank {field_name}."
            )
