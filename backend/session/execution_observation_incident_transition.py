from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_observation_incident_transition_error import (
    ExecutionObservationIncidentTransitionError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "OPEN",
        "ACKNOWLEDGED",
        "ESCALATED",
        "RESOLVED",
    }
)


@dataclass(frozen=True)
class ExecutionObservationIncidentTransition:
    """
    Immutable record of an incident's lifecycle status changing from
    one value to another.

    The transition is a value object only. It performs no state
    tracking of its own; acknowledging, escalating, and resolving an
    incident, and looking up its status and transition history, is
    the responsibility of an execution observation incident
    lifecycle service.

    Attributes:
        transition_id: The transition's unique identifier
        incident_id: The identifier of the incident that
            transitioned
        from_status: The incident's status immediately before this
            transition
        to_status: The incident's status immediately after this
            transition; always different from from_status
        actor: Who or what performed this transition
        timestamp: When this transition occurred
    """

    incident_id: str

    from_status: str

    to_status: str

    actor: str

    transition_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.transition_id, "transition ID")
        self._require_text(self.incident_id, "incident ID")
        self._require_text(self.actor, "actor")
        self._require_status(self.from_status, "from status")
        self._require_status(self.to_status, "to status")

        if self.from_status == self.to_status:
            raise ExecutionObservationIncidentTransitionError(
                "Cannot build an execution observation incident transition with an unchanged status."
            )

        if not isinstance(self.timestamp, datetime):
            raise ExecutionObservationIncidentTransitionError(
                "Cannot build an execution observation incident transition with a non-datetime timestamp."
            )

    def _require_status(self, value, field_name: str) -> None:
        self._require_text(value, field_name)

        if value not in SUPPORTED_STATUSES:
            raise ExecutionObservationIncidentTransitionError(
                f"Unsupported {field_name} {value!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationIncidentTransitionError(
                f"Cannot build an execution observation incident transition with an empty or blank {field_name}."
            )
