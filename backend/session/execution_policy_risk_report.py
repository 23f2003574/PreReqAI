from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_policy_risk_report_error import (
    ExecutionPolicyRiskReportError,
)

from .execution_policy_risk_score import (
    LEVELS,
    MAX_SCORE,
    level_for_score,
)


@dataclass(frozen=True)
class ExecutionPolicyRiskReport:
    """
    Immutable snapshot combining a session's policy evaluation,
    conflicts, active overrides, and risk score at a point in time.

    The report is a value object only. It performs no calculation of
    its own; gathering the current picture from the evaluation,
    conflict, risk, and override services and producing this record
    is the responsibility of an execution policy risk report
    service. Once generated, a report is never edited: a later
    change to any underlying service produces a new report, never a
    mutation of an old one.

    Attributes:
        report_id: The report's unique identifier
        session_id: The identifier of the execution session this
            report was generated for
        risk_score: The session's risk score at generation time, per
            execution_policy_risk_score.MAX_SCORE
        risk_level: The level risk_score falls into, per
            execution_policy_risk_score.level_for_score()
        violations: Every violation found across the session's
            evaluated policies at generation time, in a fixed,
            sorted order
        conflicts: The identifiers of every unresolved conflict for
            the session at generation time, in a fixed, sorted order
        overrides: The identifiers of every active risk override for
            the session at generation time, in a fixed, sorted order
        generated_at: When this report was generated
    """

    report_id: str

    session_id: str

    risk_score: int

    risk_level: str

    violations: tuple

    conflicts: tuple

    overrides: tuple

    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.report_id, "report ID")
        self._require_text(self.session_id, "session ID")

        if not isinstance(self.risk_score, int) or isinstance(self.risk_score, bool):
            raise ExecutionPolicyRiskReportError(
                "Cannot build an execution policy risk report with a non-int risk_score."
            )

        if self.risk_score < 0 or self.risk_score > MAX_SCORE:
            raise ExecutionPolicyRiskReportError(
                f"Cannot build an execution policy risk report with a risk_score outside 0-{MAX_SCORE}."
            )

        if self.risk_level not in LEVELS:
            raise ExecutionPolicyRiskReportError(
                f"Cannot build an execution policy risk report with an unknown risk_level: {self.risk_level!r}."
            )

        if self.risk_level != level_for_score(self.risk_score):
            raise ExecutionPolicyRiskReportError(
                f"Cannot build an execution policy risk report of {self.risk_score} with mismatched risk_level {self.risk_level!r}."
            )

        object.__setattr__(self, "violations", self._normalized(self.violations, "violation"))
        object.__setattr__(self, "conflicts", self._normalized(self.conflicts, "conflict ID"))
        object.__setattr__(self, "overrides", self._normalized(self.overrides, "override ID"))

        if not isinstance(self.generated_at, datetime):
            raise ExecutionPolicyRiskReportError(
                "Cannot build an execution policy risk report with a non-datetime generated_at."
            )

    def _normalized(self, values, field_name: str) -> tuple:
        if values is None:
            raise ExecutionPolicyRiskReportError(
                f"Cannot build an execution policy risk report with a None {field_name} collection."
            )

        values_list = list(values)

        for value in values_list:
            if not isinstance(value, str) or not value.strip():
                raise ExecutionPolicyRiskReportError(
                    f"Cannot build an execution policy risk report with a blank {field_name}."
                )

        return tuple(values_list)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyRiskReportError(
                f"Cannot build an execution policy risk report with an empty or blank {field_name}."
            )
