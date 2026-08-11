from dataclasses import (
    dataclass,
    field,
)

from uuid import uuid4

from .execution_observation_correlation_rule_error import (
    ExecutionObservationCorrelationRuleError,
)


@dataclass(frozen=True)
class ExecutionObservationCorrelationRule:
    """
    Immutable configuration describing how to automatically correlate
    observation events into incidents.

    The rule is a value object only. It performs no matching or
    correlation of its own; registering a rule, matching it against
    an event, and evaluating it against a session's events is the
    responsibility of an execution observation incident correlation
    service.

    Attributes:
        rule_id: The rule's unique identifier
        event_types: Which observation event types this rule matches
        severity: The severity assigned to an incident opened because
            of this rule
        enabled: Whether this rule is evaluated at all; a disabled
            rule never matches anything
    """

    event_types: tuple

    severity: str

    enabled: bool = True

    rule_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.rule_id, "rule ID")
        self._require_text(self.severity, "severity")

        if not isinstance(self.enabled, bool):
            raise ExecutionObservationCorrelationRuleError(
                "Cannot build an execution observation correlation rule with a non-bool enabled."
            )

        if self.event_types is None:
            raise ExecutionObservationCorrelationRuleError(
                "Cannot build an execution observation correlation rule with a None event_types."
            )

        event_type_list = list(self.event_types)

        if not event_type_list:
            raise ExecutionObservationCorrelationRuleError(
                "Cannot build an execution observation correlation rule with an empty event_types."
            )

        for event_type in event_type_list:
            self._require_text(event_type, "event type")

        if len(set(event_type_list)) != len(event_type_list):
            raise ExecutionObservationCorrelationRuleError(
                "Cannot build an execution observation correlation rule with duplicate event types."
            )

        object.__setattr__(self, "event_types", tuple(event_type_list))

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationCorrelationRuleError(
                f"Cannot build an execution observation correlation rule with an empty or blank {field_name}."
            )
