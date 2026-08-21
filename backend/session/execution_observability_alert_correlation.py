from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_observability_alert_correlation_error import (
    ExecutionObservabilityAlertCorrelationError,
)

STATUS_ACTIVE = "ACTIVE"

STATUS_RESOLVED = "RESOLVED"

STATUSES = (
    STATUS_ACTIVE,
    STATUS_RESOLVED,
)


@dataclass(frozen=True)
class ExecutionObservabilityAlertCorrelation:
    """
    Immutable record grouping related alerts, possibly spanning
    multiple runtimes, into a single observable event chain
    representing one underlying incident.

    The correlation is a value object only. It performs no grouping
    of its own; correlating and resolving is the responsibility of an
    execution alert correlation service, which produces a new record
    for every transition rather than mutating an existing one.

    Attributes:
        correlation_id: The correlation's unique identifier
        alert_ids: The identifiers of every alert grouped into this
            correlation, earliest-triggered first
        runtime_ids: The identifiers of every runtime any grouped
            alert belongs to
        root_alert_id: The identifier of the earliest alert, treated
            as the incident's root cause; always a member of
            alert_ids
        status: The correlation's current state, one of STATUSES
        created_at: When this correlation was formed
    """

    alert_ids: tuple

    runtime_ids: tuple

    root_alert_id: str

    correlation_id: str = field(default_factory=lambda: str(uuid4()))

    status: str = STATUS_ACTIVE

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.correlation_id, "correlation ID")
        self._require_text(self.root_alert_id, "root alert ID")

        self._require_id_tuple(self.alert_ids, "alert_ids")
        self._require_id_tuple(self.runtime_ids, "runtime_ids")

        if self.root_alert_id not in self.alert_ids:
            raise ExecutionObservabilityAlertCorrelationError(
                "Cannot build an execution observability alert correlation whose root_alert_id "
                "is not a member of alert_ids."
            )

        if self.status not in STATUSES:
            raise ExecutionObservabilityAlertCorrelationError(
                f"Cannot build an execution observability alert correlation with an unknown status: "
                f"{self.status!r}."
            )

        if self.created_at is None or not isinstance(self.created_at, datetime):
            raise ExecutionObservabilityAlertCorrelationError(
                "Cannot build an execution observability alert correlation with a non-datetime created_at."
            )

    @classmethod
    def _require_id_tuple(cls, value, field_name: str) -> None:
        if not isinstance(value, tuple) or not value:
            raise ExecutionObservabilityAlertCorrelationError(
                f"Cannot build an execution observability alert correlation with an empty {field_name}."
            )

        for item in value:
            cls._require_text(item, f"{field_name} entry")

        if len(set(value)) != len(value):
            raise ExecutionObservabilityAlertCorrelationError(
                f"Cannot build an execution observability alert correlation with duplicate {field_name}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityAlertCorrelationError(
                f"Cannot build an execution observability alert correlation with an empty or blank {field_name}."
            )
