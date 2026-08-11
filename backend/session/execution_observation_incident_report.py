from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_observation_incident_report_error import (
    ExecutionObservationIncidentReportError,
)

from .execution_observation_incident_transition import (
    ExecutionObservationIncidentTransition,
)


@dataclass(frozen=True)
class ExecutionObservationIncidentReport:
    """
    Immutable snapshot combining an incident's correlated events and
    its complete lifecycle transition history, including any
    escalations, as of the moment it was generated.

    The report is a value object only. It performs no assembly of
    its own; generating a report, retrieving one, listing an
    incident's report history, and comparing two reports is the
    responsibility of an execution observation incident report
    service.

    Attributes:
        report_id: The report's unique identifier
        incident_id: The identifier of the incident this report
            covers
        severity: The incident's severity as of generated_at
        events: The incident's correlated event IDs, in the order
            they were correlated
        transitions: The incident's complete lifecycle transition
            history, in chronological order
        generated_at: When this report was generated
    """

    incident_id: str

    severity: str

    events: tuple = field(
        default_factory=tuple,
    )

    transitions: tuple = field(
        default_factory=tuple,
    )

    report_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.report_id, "report ID")
        self._require_text(self.incident_id, "incident ID")
        self._require_text(self.severity, "severity")

        if not isinstance(self.generated_at, datetime):
            raise ExecutionObservationIncidentReportError(
                "Cannot build an execution observation incident report with a non-datetime generated_at."
            )

        if self.events is None:
            raise ExecutionObservationIncidentReportError(
                "Cannot build an execution observation incident report with a None events."
            )

        event_list = list(self.events)

        for event_id in event_list:
            self._require_text(event_id, "event ID")

        object.__setattr__(self, "events", tuple(event_list))

        if self.transitions is None:
            raise ExecutionObservationIncidentReportError(
                "Cannot build an execution observation incident report with a None transitions."
            )

        transition_list = list(self.transitions)

        for transition in transition_list:
            if not isinstance(transition, ExecutionObservationIncidentTransition):
                raise ExecutionObservationIncidentReportError(
                    "Cannot build an execution observation incident report with a non-"
                    "ExecutionObservationIncidentTransition transition."
                )

        object.__setattr__(self, "transitions", tuple(transition_list))

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationIncidentReportError(
                f"Cannot build an execution observation incident report with an empty or blank {field_name}."
            )
