from dataclasses import (
    dataclass,
    field,
)

from numbers import (
    Real,
)

from uuid import uuid4

from .execution_observability_alert_rule_error import (
    ExecutionObservabilityAlertRuleError,
)

from .execution_observability_event import (
    SEVERITIES,
)

OPERATOR_GT = "GT"

OPERATOR_GTE = "GTE"

OPERATOR_LT = "LT"

OPERATOR_LTE = "LTE"

OPERATOR_EQ = "EQ"

OPERATORS = (
    OPERATOR_GT,
    OPERATOR_GTE,
    OPERATOR_LT,
    OPERATOR_LTE,
    OPERATOR_EQ,
)


@dataclass(frozen=True)
class ExecutionObservabilityAlertRule:
    """
    Immutable definition of a rule that turns an abnormal runtime
    metric into an actionable alert.

    The rule is a value object only. It performs no evaluation of its
    own; registering rules and evaluating them against current
    observability data is the responsibility of an execution alert
    rule service, which produces a new record for every transition
    (such as disabling a rule) rather than mutating an existing one.

    Attributes:
        rule_id: The rule's unique identifier
        name: A human-readable name for the rule
        metric: The name of the metric this rule watches
        operator: The comparison applied to the metric's latest
            value, one of OPERATORS
        threshold: The numeric value the metric is compared against
        severity: The alert's severity when triggered, one of
            SEVERITIES
        enabled: Whether the rule is currently active
    """

    name: str

    metric: str

    operator: str

    threshold: float

    severity: str

    rule_id: str = field(default_factory=lambda: str(uuid4()))

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.rule_id, "rule ID")
        self._require_text(self.name, "name")
        self._require_text(self.metric, "metric")

        if self.operator not in OPERATORS:
            raise ExecutionObservabilityAlertRuleError(
                f"Cannot build an execution observability alert rule with an unknown operator: {self.operator!r}."
            )

        if isinstance(self.threshold, bool) or not isinstance(self.threshold, Real):
            raise ExecutionObservabilityAlertRuleError(
                f"Cannot build an execution observability alert rule with a non-numeric threshold: "
                f"{self.threshold!r}."
            )

        if self.severity not in SEVERITIES:
            raise ExecutionObservabilityAlertRuleError(
                f"Cannot build an execution observability alert rule with an unknown severity: {self.severity!r}."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionObservabilityAlertRuleError(
                "Cannot build an execution observability alert rule with a non-boolean enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityAlertRuleError(
                f"Cannot build an execution observability alert rule with an empty or blank {field_name}."
            )
