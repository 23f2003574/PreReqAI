from threading import (
    RLock,
)

from uuid import uuid4

from .execution_policy_risk_report import (
    ExecutionPolicyRiskReport,
)

from .execution_policy_risk_report_error import (
    ExecutionPolicyRiskReportError,
)


class ExecutionPolicyRiskReportService:
    """
    Generates immutable reports combining a session's policy
    evaluation, conflicts, active risk overrides, and risk score,
    using an existing execution policy evaluation service, conflict
    service, risk service, and risk override service as the sources
    of truth for each.

    Behavior:
    - generate() reads the complete current picture in one pass and
      records a new, immutable ExecutionPolicyRiskReport; it never
      edits a previously generated report
    - A session with no recorded evaluation history is unknown to
      this service and rejected outright
    - violations, conflicts, and overrides are always produced in a
      fixed, sorted order, so generate() is deterministic for the
      same underlying state
    - compare() reports the differences between two previously
      generated reports

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        execution_policy_evaluation_service,
        execution_policy_conflict_service,
        execution_policy_risk_service,
        execution_policy_risk_override_service,
    ):
        """
        Args:
            execution_policy_evaluation_service: Read via
                `history(session_id)` for the session's evaluated
                policies and their violations
            execution_policy_conflict_service: Read via
                `unresolved(session_id)` for the session's unresolved
                conflicts
            execution_policy_risk_service: Read via
                `calculate(session_id)` for the session's current
                risk score and level
            execution_policy_risk_override_service: Read via
                `active(session_id)` for the session's currently
                active risk overrides
        """

        self._execution_policy_evaluation_service = execution_policy_evaluation_service
        self._execution_policy_conflict_service = execution_policy_conflict_service
        self._execution_policy_risk_service = execution_policy_risk_service
        self._execution_policy_risk_override_service = execution_policy_risk_override_service
        self._reports_by_id = {}
        self._report_ids_by_session = {}
        self._lock = RLock()

    def generate(self, session_id: str) -> ExecutionPolicyRiskReport:
        """
        Generate a new report for a session.

        Raises:
            ExecutionPolicyRiskReportError: If session_id is None or
                blank, or no evaluation has ever been recorded for it
        """

        self._validate_text(session_id, "session ID")

        with self._lock:
            evaluations = self._execution_policy_evaluation_service.history(session_id)

            if not evaluations:
                raise ExecutionPolicyRiskReportError(f"Session ID {session_id!r} is unknown: it has never been evaluated.")

            latest_by_policy = {}
            for evaluation in evaluations:
                latest_by_policy[evaluation.policy_id] = evaluation

            violations = tuple(
                sorted(
                    f"{policy_id}:{violation}"
                    for policy_id, evaluation in latest_by_policy.items()
                    for violation in evaluation.violations
                )
            )

            conflicts = tuple(
                sorted(
                    conflict.conflict_id
                    for conflict in self._execution_policy_conflict_service.unresolved(session_id)
                )
            )

            overrides = tuple(
                sorted(
                    override.override_id
                    for override in self._execution_policy_risk_override_service.active(session_id)
                )
            )

            risk_score = self._execution_policy_risk_service.calculate(session_id)

            report = ExecutionPolicyRiskReport(
                report_id=str(uuid4()),
                session_id=session_id,
                risk_score=risk_score.score,
                risk_level=risk_score.level,
                violations=violations,
                conflicts=conflicts,
                overrides=overrides,
            )

            self._reports_by_id[report.report_id] = report
            self._report_ids_by_session.setdefault(session_id, []).append(report.report_id)

            return report

    def get(self, report_id: str) -> ExecutionPolicyRiskReport:
        """
        Look up a previously generated report.

        Raises:
            ExecutionPolicyRiskReportError: If report_id is None or
                blank, or no report is recorded under it
        """

        self._validate_text(report_id, "report ID")

        with self._lock:
            return self._resolve(report_id)

    def history(self, session_id: str) -> list:
        """
        List every report generated for a session, in the order
        generate() produced them.

        Raises:
            ExecutionPolicyRiskReportError: If session_id is None or
                blank
        """

        self._validate_text(session_id, "session ID")

        with self._lock:
            return [
                self._reports_by_id[report_id] for report_id in self._report_ids_by_session.get(session_id, [])
            ]

    def compare(self, report_a: str, report_b: str) -> dict:
        """
        Compare two previously generated reports.

        Raises:
            ExecutionPolicyRiskReportError: If report_a or report_b
                is None or blank, or either has no report recorded
                under it
        """

        self._validate_text(report_a, "report_a")
        self._validate_text(report_b, "report_b")

        with self._lock:
            first = self._resolve(report_a)
            second = self._resolve(report_b)

            return {
                "risk_score_delta": second.risk_score - first.risk_score,
                "risk_level_changed": first.risk_level != second.risk_level,
                "new_violations": tuple(sorted(set(second.violations) - set(first.violations))),
                "resolved_violations": tuple(sorted(set(first.violations) - set(second.violations))),
                "new_conflicts": tuple(sorted(set(second.conflicts) - set(first.conflicts))),
                "resolved_conflicts": tuple(sorted(set(first.conflicts) - set(second.conflicts))),
            }

    def _resolve(self, report_id: str) -> ExecutionPolicyRiskReport:
        report = self._reports_by_id.get(report_id)

        if report is None:
            raise ExecutionPolicyRiskReportError(f"No report is recorded under report ID {report_id!r}.")

        return report

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyRiskReportError(f"Cannot use an empty or blank {field_name}.")
