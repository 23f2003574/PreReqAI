from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_governance_report_error import (
    ExecutionGovernanceReportError,
)


@dataclass(frozen=True)
class ExecutionGovernanceReport:
    """
    Immutable snapshot combining a change request's approval,
    compliance, certification, and exception state at a point in
    time.

    The report is a value object only. It performs no calculation of
    its own; gathering the current picture from an approval,
    compliance, certification, and exception service and producing
    this record is the responsibility of an execution governance
    report service. Once generated, a report is never edited: a
    later change to any underlying service produces a new report,
    never a mutation of an old one.

    Attributes:
        report_id: The report's unique identifier
        change_id: The identifier of the change request this report
            was generated for
        approval_status: The change request's approval status at
            generation time
        compliance_status: The change request's compliance status at
            generation time
        certification_status: The change request's certification
            status at generation time
        exceptions: The identifiers of every active compliance
            exception for the change request at generation time, in a
            fixed, sorted order
        generated_at: When this report was generated
    """

    report_id: str

    change_id: str

    approval_status: str

    compliance_status: str

    certification_status: str

    exceptions: tuple

    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.report_id, "report ID")
        self._require_text(self.change_id, "change ID")
        self._require_text(self.approval_status, "approval_status")
        self._require_text(self.compliance_status, "compliance_status")
        self._require_text(self.certification_status, "certification_status")

        object.__setattr__(self, "exceptions", self._normalized(self.exceptions, "exception ID"))

        if not isinstance(self.generated_at, datetime):
            raise ExecutionGovernanceReportError(
                "Cannot build an execution governance report with a non-datetime generated_at."
            )

    def _normalized(self, values, field_name: str) -> tuple:
        if values is None:
            raise ExecutionGovernanceReportError(
                f"Cannot build an execution governance report with a None {field_name} collection."
            )

        values_list = list(values)

        for value in values_list:
            if not isinstance(value, str) or not value.strip():
                raise ExecutionGovernanceReportError(
                    f"Cannot build an execution governance report with a blank {field_name}."
                )

        return tuple(values_list)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionGovernanceReportError(
                f"Cannot build an execution governance report with an empty or blank {field_name}."
            )
