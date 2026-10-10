from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_observation_incident_error import (
    ExecutionObservationIncidentError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "ACTIVE",
        "RESOLVED",
    }
)


@dataclass(frozen=True)
class ExecutionObservationIncident:
    """
    Immutable snapshot of an incident correlating a set of
    observation events (errors, alerts, health transitions) into one
    actionable unit.

    The incident is a value object only. It performs no correlation
    of its own; opening an incident, adding events to it, resolving
    it, and looking up active or historical incidents is the
    responsibility of an execution observation incident service.

    Attributes:
        incident_id: The incident's unique identifier
        session_id: The identifier of the execution session the
            incident belongs to
        severity: How severe this incident is, e.g. "LOW" or
            "CRITICAL"
        event_ids: The distinct observation event IDs correlated to
            this incident, in the order they were added
        status: The incident's current status, one of ACTIVE or
            RESOLVED
        opened_at: When this incident was opened
        resolved_at: When this incident was resolved, or None while
            it is still ACTIVE
    """

    session_id: str

    severity: str

    event_ids: tuple = field(
        default_factory=tuple,
    )

    status: str = "ACTIVE"

    incident_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    opened_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    resolved_at: datetime | None = None

    def __post_init__(self):
        self._require_text(self.incident_id, "incident ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.severity, "severity")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionObservationIncidentError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if not isinstance(self.opened_at, datetime):
            raise ExecutionObservationIncidentError(
                "Cannot build an execution observation incident with a non-datetime opened_at."
            )

        if self.event_ids is None:
            raise ExecutionObservationIncidentError(
                "Cannot build an execution observation incident with a None event_ids."
            )

        event_id_list = list(self.event_ids)

        for event_id in event_id_list:
            self._require_text(event_id, "event ID")

        if len(set(event_id_list)) != len(event_id_list):
            raise ExecutionObservationIncidentError(
                "Cannot build an execution observation incident with duplicate event IDs."
            )

        object.__setattr__(self, "event_ids", tuple(event_id_list))

        if self.status == "ACTIVE":
            if self.resolved_at is not None:
                raise ExecutionObservationIncidentError(
                    "Cannot build an execution observation incident that is ACTIVE with a resolved_at set."
                )
        else:
            if not isinstance(self.resolved_at, datetime):
                raise ExecutionObservationIncidentError(
                    "Cannot build a RESOLVED execution observation incident with a non-datetime resolved_at."
                )

            if self.resolved_at < self.opened_at:
                raise ExecutionObservationIncidentError(
                    "Cannot build an execution observation incident with a resolved_at before opened_at."
                )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationIncidentError(
                f"Cannot build an execution observation incident with an empty or blank {field_name}."
            )
