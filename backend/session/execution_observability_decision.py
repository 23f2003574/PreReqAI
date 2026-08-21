from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_observability_decision_error import (
    ExecutionObservabilityDecisionError,
)

STATUS_HEALTHY = "HEALTHY"

STATUS_WARNING = "WARNING"

STATUS_CRITICAL = "CRITICAL"

STATUSES = (
    STATUS_HEALTHY,
    STATUS_WARNING,
    STATUS_CRITICAL,
)


@dataclass(frozen=True)
class ExecutionObservabilityDecision:
    """
    Immutable, single-point-in-time verdict combining every
    observability signal for a runtime (alerts, escalation, and
    analytics) into one overall status.

    The decision is a value object only. It performs no aggregation
    of its own; computing it from a runtime's current observability
    state is the responsibility of an execution observability
    orchestration service, which produces a new record for every
    decision() call rather than mutating an existing one.

    Attributes:
        decision_id: The decision's unique identifier
        runtime_id: The identifier of the runtime this decision
            describes
        status: The runtime's overall observability status, one of
            STATUSES
        alert_count: How many alerts are currently OPEN for the
            runtime
        health_summary: The escalation and analytics detail this
            status was derived from
        created_at: When this decision was computed
    """

    runtime_id: str

    status: str

    alert_count: int

    health_summary: dict

    decision_id: str = field(default_factory=lambda: str(uuid4()))

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.decision_id, "decision ID")
        self._require_text(self.runtime_id, "runtime ID")

        if self.status not in STATUSES:
            raise ExecutionObservabilityDecisionError(
                f"Cannot build an execution observability decision with an unknown status: {self.status!r}."
            )

        if isinstance(self.alert_count, bool) or not isinstance(self.alert_count, int) or self.alert_count < 0:
            raise ExecutionObservabilityDecisionError(
                f"Cannot build an execution observability decision with a negative or non-integer "
                f"alert_count: {self.alert_count!r}."
            )

        if not isinstance(self.health_summary, dict):
            raise ExecutionObservabilityDecisionError(
                "Cannot build an execution observability decision with a non-dict health_summary."
            )

        if self.created_at is None or not isinstance(self.created_at, datetime):
            raise ExecutionObservabilityDecisionError(
                "Cannot build an execution observability decision with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityDecisionError(
                f"Cannot build an execution observability decision with an empty or blank {field_name}."
            )
