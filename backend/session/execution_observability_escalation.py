from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_observability_escalation_error import (
    ExecutionObservabilityEscalationError,
)

LEVEL_WARNING = "WARNING"

LEVEL_URGENT = "URGENT"

LEVEL_CRITICAL = "CRITICAL"

LEVELS = (
    LEVEL_WARNING,
    LEVEL_URGENT,
    LEVEL_CRITICAL,
)

STATUS_ACTIVE = "ACTIVE"

STATUS_RESOLVED = "RESOLVED"

STATUSES = (
    STATUS_ACTIVE,
    STATUS_RESOLVED,
)


@dataclass(frozen=True)
class ExecutionObservabilityEscalation:
    """
    Immutable record of a single escalation raised against an
    unresolved alert whose severity requires intervention.

    The escalation is a value object only. It performs no lifecycle
    accounting of its own; escalating and resolving is the
    responsibility of an execution alert escalation service, which
    produces a new record for every transition rather than mutating
    an existing one.

    Attributes:
        escalation_id: The escalation's unique identifier
        alert_id: The identifier of the alert this escalation was
            raised against
        level: The escalation's severity tier, one of LEVELS
        reason: A human-readable explanation of why the escalation
            was raised
        escalated_at: When the escalation was raised
        status: The escalation's current state, one of STATUSES
    """

    alert_id: str

    level: str

    reason: str

    escalation_id: str = field(default_factory=lambda: str(uuid4()))

    escalated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    status: str = STATUS_ACTIVE

    def __post_init__(self):
        self._require_text(self.escalation_id, "escalation ID")
        self._require_text(self.alert_id, "alert ID")
        self._require_text(self.reason, "reason")

        if self.level not in LEVELS:
            raise ExecutionObservabilityEscalationError(
                f"Cannot build an execution observability escalation with an unknown level: {self.level!r}."
            )

        if self.status not in STATUSES:
            raise ExecutionObservabilityEscalationError(
                f"Cannot build an execution observability escalation with an unknown status: {self.status!r}."
            )

        if self.escalated_at is None or not isinstance(self.escalated_at, datetime):
            raise ExecutionObservabilityEscalationError(
                "Cannot build an execution observability escalation with a non-datetime escalated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityEscalationError(
                f"Cannot build an execution observability escalation with an empty or blank {field_name}."
            )
