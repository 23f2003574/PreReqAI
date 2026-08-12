from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import Any

from uuid import uuid4

from .execution_secret_report_error import (
    ExecutionSecretReportError,
)

from .execution_secret_security_posture import (
    ExecutionSecretSecurityPosture,
)


@dataclass(frozen=True)
class ExecutionSecretSecurityReport:
    """
    Immutable snapshot combining a secret's security posture,
    unresolved violations and anomalies, and audit summary at the
    moment it was generated.

    The report is a value object only. It performs no computation of
    its own; generating, looking up, and comparing reports is the
    responsibility of an execution secret security report service.

    Attributes:
        report_id: The report's unique identifier
        secret_id: The identifier of the secret this report was
            generated for
        posture: The secret's security posture at generation time
        violations: Every unresolved policy violation and anomaly
            found at generation time
        audit_summary: A summary of the secret's recorded audit
            history at generation time
        generated_at: When this report was generated
    """

    secret_id: str

    posture: ExecutionSecretSecurityPosture

    violations: tuple

    audit_summary: dict[str, Any]

    report_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.report_id, "report ID")
        self._require_text(self.secret_id, "secret ID")

        if not isinstance(self.posture, ExecutionSecretSecurityPosture):
            raise ExecutionSecretReportError(
                "Cannot build an execution secret security report with a posture that is not an "
                "ExecutionSecretSecurityPosture."
            )

        if self.posture.secret_id != self.secret_id:
            raise ExecutionSecretReportError(
                f"Cannot build an execution secret security report for secret ID {self.secret_id!r} with a "
                f"posture computed for secret ID {self.posture.secret_id!r}."
            )

        if self.violations is None:
            raise ExecutionSecretReportError(
                "Cannot build an execution secret security report with a None violations."
            )

        violations_list = list(self.violations)

        if any(not isinstance(violation, str) or not violation.strip() for violation in violations_list):
            raise ExecutionSecretReportError(
                "Cannot build an execution secret security report with a blank or non-string violation."
            )

        object.__setattr__(self, "violations", tuple(violations_list))

        if not isinstance(self.audit_summary, dict):
            raise ExecutionSecretReportError(
                "Cannot build an execution secret security report with a non-dict audit_summary."
            )

        if not isinstance(self.generated_at, datetime):
            raise ExecutionSecretReportError(
                "Cannot build an execution secret security report with a non-datetime generated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretReportError(
                f"Cannot build an execution secret security report with an empty or blank {field_name}."
            )
