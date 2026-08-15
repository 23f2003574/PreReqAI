from threading import (
    RLock,
)

from uuid import uuid4

from .execution_governance_report import (
    ExecutionGovernanceReport,
)

from .execution_governance_report_error import (
    ExecutionGovernanceReportError,
)

COMPLIANCE_STATUS_COMPLIANT = "COMPLIANT"

COMPLIANCE_STATUS_NON_COMPLIANT = "NON_COMPLIANT"

COMPLIANCE_STATUS_NOT_EVALUATED = "NOT_EVALUATED"

CERTIFICATION_STATUS_NOT_CERTIFIED = "NOT_CERTIFIED"


class ExecutionGovernanceReportService:
    """
    Generates immutable reports combining a change request's
    approval, compliance, certification, and exception state, using
    an existing change request (approval) service, compliance
    service, certification service, and exception service as the
    sources of truth for each.

    Behavior:
    - generate() reads the complete current picture in one pass and
      records a new, immutable ExecutionGovernanceReport; it never
      edits a previously generated report
    - A change request unknown to the approval service is rejected
      outright; compliance or certification state that has simply
      never been evaluated or certified yet is reported as
      NOT_EVALUATED or NOT_CERTIFIED rather than treated as an error
    - exceptions is always produced in a fixed, sorted order, so
      generate() is deterministic for the same underlying state
    - compare() reports the differences between two previously
      generated reports

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, approval_service, compliance_service, certification_service, exception_service):
        """
        Args:
            approval_service: Read via `status(change_id)` for the
                change request's approval status; used to confirm the
                change request exists at all
            compliance_service: Read via `can_approve(change_id)` for
                whether the change request currently satisfies
                compliance
            certification_service: Read via `status(change_id)` for
                the change request's certification status
            exception_service: Read via `active(change_id)` for the
                change request's currently active compliance
                exceptions
        """

        for name, service in (
            ("approval_service", approval_service),
            ("compliance_service", compliance_service),
            ("certification_service", certification_service),
            ("exception_service", exception_service),
        ):
            if service is None:
                raise ExecutionGovernanceReportError(
                    f"Cannot initialize execution governance report service with a None {name}."
                )

        self._approval_service = approval_service
        self._compliance_service = compliance_service
        self._certification_service = certification_service
        self._exception_service = exception_service
        self._reports_by_id = {}
        self._report_ids_by_change = {}
        self._lock = RLock()

    def generate(self, change_id: str) -> ExecutionGovernanceReport:
        """
        Generate a new report for a change request.

        Raises:
            ExecutionGovernanceReportError: If change_id is None or
                blank, or no change request is known to the approval
                service under it
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            try:
                approval_status = self._approval_service.status(change_id)
            except Exception as error:
                raise ExecutionGovernanceReportError(
                    f"Cannot generate a report for change ID {change_id!r}: it is unknown."
                ) from error

            try:
                compliant = self._compliance_service.can_approve(change_id)
                compliance_status = COMPLIANCE_STATUS_COMPLIANT if compliant else COMPLIANCE_STATUS_NON_COMPLIANT
            except Exception:
                compliance_status = COMPLIANCE_STATUS_NOT_EVALUATED

            try:
                certification_status = self._certification_service.status(change_id)
            except Exception:
                certification_status = CERTIFICATION_STATUS_NOT_CERTIFIED

            exceptions = tuple(
                sorted(exception.exception_id for exception in self._exception_service.active(change_id))
            )

            report = ExecutionGovernanceReport(
                report_id=str(uuid4()),
                change_id=change_id,
                approval_status=approval_status,
                compliance_status=compliance_status,
                certification_status=certification_status,
                exceptions=exceptions,
            )

            self._reports_by_id[report.report_id] = report
            self._report_ids_by_change.setdefault(change_id, []).append(report.report_id)

            return report

    def get(self, report_id: str) -> ExecutionGovernanceReport:
        """
        Look up a previously generated report.

        Raises:
            ExecutionGovernanceReportError: If report_id is None or
                blank, or no report is recorded under it
        """

        self._validate_text(report_id, "report ID")

        with self._lock:
            return self._resolve(report_id)

    def history(self, change_id: str) -> list:
        """
        List every report generated for a change request, in the
        order generate() produced them.

        Raises:
            ExecutionGovernanceReportError: If change_id is None or
                blank
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            return [self._reports_by_id[report_id] for report_id in self._report_ids_by_change.get(change_id, [])]

    def compare(self, report_a: str, report_b: str) -> dict:
        """
        Compare two previously generated reports.

        Raises:
            ExecutionGovernanceReportError: If report_a or report_b
                is None or blank, or either has no report recorded
                under it
        """

        self._validate_text(report_a, "report_a")
        self._validate_text(report_b, "report_b")

        with self._lock:
            first = self._resolve(report_a)
            second = self._resolve(report_b)

            return {
                "approval_status_changed": first.approval_status != second.approval_status,
                "compliance_status_changed": first.compliance_status != second.compliance_status,
                "certification_status_changed": first.certification_status != second.certification_status,
                "new_exceptions": tuple(sorted(set(second.exceptions) - set(first.exceptions))),
                "resolved_exceptions": tuple(sorted(set(first.exceptions) - set(second.exceptions))),
            }

    def _resolve(self, report_id: str) -> ExecutionGovernanceReport:
        report = self._reports_by_id.get(report_id)

        if report is None:
            raise ExecutionGovernanceReportError(f"No report is recorded under report ID {report_id!r}.")

        return report

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionGovernanceReportError(f"Cannot use an empty or blank {field_name}.")
