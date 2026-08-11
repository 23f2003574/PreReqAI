from threading import (
    RLock,
)

from .execution_observation_incident_report_error import (
    ExecutionObservationIncidentReportError,
)

from .execution_observation_incident_report import (
    ExecutionObservationIncidentReport,
)


class ExecutionObservationIncidentReportService:
    """
    Generates immutable reports combining an incident's correlated
    events and its complete lifecycle transition history (including
    any escalations). Incidents, lifecycle transitions, and
    escalations are assumed to already exist in the injected
    services; this service only reads from them.

    Behavior:
    - generate() captures a complete, immutable snapshot: every
      currently correlated event ID and the incident's entire
      lifecycle transition history, in the order those services
      already return them
    - No method ever edits a report once generated; a later
      generate() call for the same incident produces a new, distinct
      report reflecting the incident's state at that later time
    - compare() is a pure read: it never mutates either report

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, incident_service, lifecycle_service):
        """
        Args:
            incident_service: The service used to read an incident's
                core data. Any object exposing `get(incident_id)`,
                returning a record with `severity` and `event_ids`
                attributes and raising if incident_id is unknown, is
                accepted
            lifecycle_service: The service used to read an incident's
                complete lifecycle transition history. Any object
                exposing `history(incident_id)`, returning
                transitions in chronological order, is accepted
        """

        self._incident_service = incident_service
        self._lifecycle_service = lifecycle_service
        self._reports_by_id = {}
        self._report_ids_by_incident = {}
        self._lock = RLock()

    def generate(self, incident_id: str) -> ExecutionObservationIncidentReport:
        """
        Generate a new report capturing an incident's currently
        correlated events and complete lifecycle transition history.

        Raises:
            ExecutionObservationIncidentReportError: If incident_id
                is None or blank, or no incident is known under it
        """

        self._validate_id(incident_id, "incident ID")

        with self._lock:
            try:
                incident = self._incident_service.get(incident_id)
            except Exception as error:
                raise ExecutionObservationIncidentReportError(
                    f"No incident is known under incident ID {incident_id!r}."
                ) from error

            report = ExecutionObservationIncidentReport(
                incident_id=incident_id,
                severity=incident.severity,
                events=tuple(incident.event_ids),
                transitions=tuple(self._lifecycle_service.history(incident_id)),
            )

            self._reports_by_id[report.report_id] = report
            self._report_ids_by_incident.setdefault(incident_id, []).append(report.report_id)

            return report

    def get(self, report_id: str) -> ExecutionObservationIncidentReport:
        """
        Look up a previously generated report.

        Raises:
            ExecutionObservationIncidentReportError: If report_id is
                None or blank, or no report is known under it
        """

        self._validate_id(report_id, "report ID")

        with self._lock:
            report = self._reports_by_id.get(report_id)

            if report is None:
                raise ExecutionObservationIncidentReportError(f"No report is known under report ID {report_id!r}.")

            return report

    def history(self, incident_id: str) -> list:
        """
        List every report generated for an incident, oldest to
        newest.

        Raises:
            ExecutionObservationIncidentReportError: If incident_id
                is None or blank
        """

        self._validate_id(incident_id, "incident ID")

        with self._lock:
            reports = [
                self._reports_by_id[report_id] for report_id in self._report_ids_by_incident.get(incident_id, [])
            ]

            return sorted(reports, key=lambda report: report.generated_at)

    def compare(
        self,
        report_a: ExecutionObservationIncidentReport,
        report_b: ExecutionObservationIncidentReport,
    ) -> dict:
        """
        Compare two reports, describing what changed from report_a to
        report_b.

        Raises:
            ExecutionObservationIncidentReportError: If report_a or
                report_b is not an ExecutionObservationIncidentReport
        """

        for report in (report_a, report_b):
            if not isinstance(report, ExecutionObservationIncidentReport):
                raise ExecutionObservationIncidentReportError(
                    "Cannot compare an invalid report: both arguments must be "
                    "ExecutionObservationIncidentReport instances."
                )

        a_event_ids = set(report_a.events)
        a_transition_ids = {transition.transition_id for transition in report_a.transitions}

        return {
            "severity_changed": report_a.severity != report_b.severity,
            "previous_severity": report_a.severity,
            "current_severity": report_b.severity,
            "new_events": tuple(event_id for event_id in report_b.events if event_id not in a_event_ids),
            "new_transitions": tuple(
                transition for transition in report_b.transitions if transition.transition_id not in a_transition_ids
            ),
        }

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationIncidentReportError(f"Cannot use an empty or blank {field_name}.")
