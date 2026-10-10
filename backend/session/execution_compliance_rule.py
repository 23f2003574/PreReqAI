from dataclasses import (
    dataclass,
)

from typing import (
    Callable,
)

from .execution_compliance_error import (
    ExecutionComplianceError,
)

SEVERITY_WARNING = "WARNING"

SEVERITY_BLOCKING = "BLOCKING"

SEVERITIES = (
    SEVERITY_WARNING,
    SEVERITY_BLOCKING,
)


@dataclass(frozen=True)
class ExecutionComplianceRule:
    """
    Immutable, reusable definition of an organizational requirement a
    governed execution change must satisfy.

    The rule is a value object only. It performs no evaluation of
    its own beyond exposing condition; running a rule against a
    change request's proposed changes, and disabling a rule, is the
    responsibility of an execution compliance service.

    Attributes:
        rule_id: The rule's unique identifier
        name: A short, human-readable name for the rule
        condition: A callable taking a change request's changes
            mapping and returning True if the changes comply with the
            rule, False if they violate it
        severity: How serious a violation of this rule is, one of
            SEVERITIES. BLOCKING violations prevent approval;
            WARNING violations do not
        enabled: Whether this rule is currently evaluated. A disabled
            rule is ignored entirely
    """

    rule_id: str

    name: str

    condition: Callable

    severity: str

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.rule_id, "rule ID")
        self._require_text(self.name, "name")

        if not callable(self.condition):
            raise ExecutionComplianceError(
                "Cannot build an execution compliance rule with a non-callable condition."
            )

        if self.severity not in SEVERITIES:
            raise ExecutionComplianceError(
                f"Cannot build an execution compliance rule with an unknown severity: {self.severity!r}."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionComplianceError(
                "Cannot build an execution compliance rule with a non-bool enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionComplianceError(
                f"Cannot build an execution compliance rule with an empty or blank {field_name}."
            )
