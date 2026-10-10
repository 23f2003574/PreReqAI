from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from numbers import (
    Real,
)

from .execution_network_endpoint_health_error import (
    ExecutionNetworkEndpointHealthError,
)

STATUS_HEALTHY = "HEALTHY"

STATUS_DEGRADED = "DEGRADED"

STATUS_UNREACHABLE = "UNREACHABLE"

STATUSES = (
    STATUS_HEALTHY,
    STATUS_DEGRADED,
    STATUS_UNREACHABLE,
)


@dataclass(frozen=True)
class ExecutionNetworkEndpointHealth:
    """
    Immutable snapshot of whether a network endpoint was reachable
    and usable at a point in time.

    The health snapshot is a value object only. It performs no
    probing of its own; computing it by measuring the endpoint's
    reachability and latency is the responsibility of an execution
    network endpoint health service, which produces a new snapshot
    for every check rather than mutating an existing one.

    Attributes:
        endpoint_id: The identifier of the endpoint this snapshot
            describes
        status: The endpoint's health verdict, one of STATUSES
        latency_ms: The measured round-trip latency, or None if the
            endpoint was unreachable
        checked_at: When this snapshot was computed
        failure_reason: Why the endpoint is not HEALTHY, or None when
            it is
    """

    endpoint_id: str

    status: str

    latency_ms: float = None

    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    failure_reason: str = None

    def __post_init__(self):
        self._require_text(self.endpoint_id, "endpoint ID")

        if self.status not in STATUSES:
            raise ExecutionNetworkEndpointHealthError(
                f"Cannot build an execution network endpoint health snapshot with an unknown "
                f"status: {self.status!r}."
            )

        if self.checked_at is None or not isinstance(self.checked_at, datetime):
            raise ExecutionNetworkEndpointHealthError(
                "Cannot build an execution network endpoint health snapshot with a non-datetime "
                "checked_at."
            )

        if self.latency_ms is not None and (
            isinstance(self.latency_ms, bool) or not isinstance(self.latency_ms, Real) or self.latency_ms < 0
        ):
            raise ExecutionNetworkEndpointHealthError(
                f"Cannot build an execution network endpoint health snapshot with an invalid "
                f"latency_ms: {self.latency_ms!r}."
            )

        if self.status == STATUS_UNREACHABLE and self.latency_ms is not None:
            raise ExecutionNetworkEndpointHealthError(
                "Cannot build an execution network endpoint health snapshot with a latency_ms "
                "for an UNREACHABLE endpoint."
            )

        if self.status != STATUS_HEALTHY and (self.failure_reason is None or not self.failure_reason.strip()):
            raise ExecutionNetworkEndpointHealthError(
                f"Cannot build an execution network endpoint health snapshot with status "
                f"{self.status!r} and no failure_reason."
            )

        if self.status == STATUS_HEALTHY and self.failure_reason is not None:
            raise ExecutionNetworkEndpointHealthError(
                "Cannot build an execution network endpoint health snapshot with a failure_reason "
                "for a HEALTHY endpoint."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkEndpointHealthError(
                f"Cannot build an execution network endpoint health snapshot with an empty or "
                f"blank {field_name}."
            )
