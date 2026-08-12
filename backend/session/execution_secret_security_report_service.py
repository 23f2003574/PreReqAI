from threading import (
    RLock,
)

from .execution_secret_report_error import (
    ExecutionSecretReportError,
)

from .execution_secret_security_report import (
    ExecutionSecretSecurityReport,
)


class ExecutionSecretSecurityReportService:
    """
    Generates an immutable security report for a secret, combining
    its current security posture, unresolved policy violations and
    anomalies, and a summary of its audit history: using an existing
    execution secret security posture service, security policy
    service, anomaly service, and audit service as the sources of
    truth for each.

    The service's responsibility is report generation and bookkeeping
    only. It never mutates any of the services it reads from; a
    generated report is a pure snapshot of whatever state already
    existed at the moment generate() was called, and once generated
    it is never rewritten.

    Behavior:
    - generate() is deterministic for the same underlying state: its
      posture, violations, and audit_summary depend only on what the
      services it reads from currently report, never on anything
      random or incidental. Only report_id and generated_at are
      unique per call
    - violations combines the secret's current policy violations with
      its currently unresolved anomalies, each rendered as
      "anomaly:<anomaly_type>:<principal>"
    - history() never loses or rewrites a past report; generate()
      only ever appends

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        execution_secret_posture_service,
        execution_secret_policy_service,
        execution_secret_anomaly_service,
        execution_secret_audit_service,
    ):
        """
        Args:
            execution_secret_posture_service: Read via
                `evaluate(secret_id)` for the secret's current
                security posture
            execution_secret_policy_service: Read via
                `violations(secret_id)` for the secret's current
                policy violations
            execution_secret_anomaly_service: Read via `active()` for
                the secret's currently unresolved anomalies
            execution_secret_audit_service: Read via
                `history(secret_id)` to summarize the secret's
                recorded audit history
        """

        self._execution_secret_posture_service = execution_secret_posture_service
        self._execution_secret_policy_service = execution_secret_policy_service
        self._execution_secret_anomaly_service = execution_secret_anomaly_service
        self._execution_secret_audit_service = execution_secret_audit_service
        self._reports_by_id = {}
        self._report_ids_by_secret = {}
        self._lock = RLock()

    def generate(self, secret_id: str) -> ExecutionSecretSecurityReport:
        """
        Generate and store a security report for a secret.

        Raises:
            ExecutionSecretReportError: If secret_id is None or blank
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            posture = self._execution_secret_posture_service.evaluate(secret_id)
            policy_violations = list(self._execution_secret_policy_service.violations(secret_id))

            anomaly_violations = [
                f"anomaly:{anomaly.anomaly_type.value}:{anomaly.principal}"
                for anomaly in self._execution_secret_anomaly_service.active()
                if anomaly.secret_id == secret_id
            ]

            report = ExecutionSecretSecurityReport(
                secret_id=secret_id,
                posture=posture,
                violations=tuple(policy_violations + anomaly_violations),
                audit_summary=self._audit_summary(secret_id),
            )

            self._reports_by_id[report.report_id] = report
            self._report_ids_by_secret.setdefault(secret_id, []).append(report.report_id)

            return report

    def get(self, report_id: str) -> ExecutionSecretSecurityReport:
        """
        Look up a previously generated report.

        Raises:
            ExecutionSecretReportError: If report_id is None or
                blank, or no report is known under it
        """

        self._validate_id(report_id, "report ID")

        with self._lock:
            return self._resolve(report_id)

    def history(self, secret_id: str) -> list:
        """
        List every report ever generated for a secret, in the order
        they were generated.

        Raises:
            ExecutionSecretReportError: If secret_id is None or blank
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            return [
                self._reports_by_id[report_id]
                for report_id in self._report_ids_by_secret.get(secret_id, [])
            ]

    def compare(self, report_a: ExecutionSecretSecurityReport, report_b: ExecutionSecretSecurityReport) -> dict:
        """
        Compare two reports for the same secret, describing how the
        secret's security standing changed between them.

        Raises:
            ExecutionSecretReportError: If report_a or report_b is
                not an ExecutionSecretSecurityReport, or they were
                generated for different secrets
        """

        for report in (report_a, report_b):
            if not isinstance(report, ExecutionSecretSecurityReport):
                raise ExecutionSecretReportError(
                    "Cannot compare an invalid report: both must be ExecutionSecretSecurityReport."
                )

        if report_a.secret_id != report_b.secret_id:
            raise ExecutionSecretReportError(
                f"Cannot compare a report for secret ID {report_a.secret_id!r} with one for secret ID "
                f"{report_b.secret_id!r}."
            )

        violations_added = sorted(set(report_b.violations) - set(report_a.violations))
        violations_removed = sorted(set(report_a.violations) - set(report_b.violations))

        return {
            "secret_id": report_a.secret_id,
            "previous_level": report_a.posture.level,
            "current_level": report_b.posture.level,
            "level_changed": report_a.posture.level != report_b.posture.level,
            "violations_added": violations_added,
            "violations_removed": violations_removed,
        }

    def _audit_summary(self, secret_id: str) -> dict:
        events = self._execution_secret_audit_service.history(secret_id)

        operation_counts = {}

        for event in events:
            operation_counts[event.operation.value] = operation_counts.get(event.operation.value, 0) + 1

        return {
            "total_events": len(events),
            "operation_counts": operation_counts,
            "last_event_at": events[-1].timestamp.isoformat() if events else None,
        }

    def _resolve(self, report_id: str) -> ExecutionSecretSecurityReport:
        report = self._reports_by_id.get(report_id)

        if report is None:
            raise ExecutionSecretReportError(f"No report is known under report ID {report_id!r}.")

        return report

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretReportError(f"Cannot use an empty or blank {field_name}.")
