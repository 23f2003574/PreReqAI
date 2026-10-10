from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_policy_enforcement_error import (
    ExecutionPolicyEnforcementError,
)


@dataclass(frozen=True)
class ExecutionPolicyDecision:
    """
    Immutable record of the final decision to authorize or deny an
    execution session, made immediately before execution dispatch.

    The decision is a value object only. It performs no enforcement
    of its own; evaluating applicable policies, applying active
    exceptions, checking for unresolved conflicts, and recording this
    record is the responsibility of an execution policy enforcement
    service.

    Attributes:
        decision_id: The decision's unique identifier
        session_id: The identifier of the execution session this
            decision was made for
        allowed: Whether the session was authorized to proceed, i.e.
            violations is empty
        violations: Every reason execution was denied, in the order
            they were found. Empty if and only if allowed is True
        evaluated_at: When this decision was made
    """

    decision_id: str

    session_id: str

    allowed: bool

    violations: tuple

    evaluated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.decision_id, "decision ID")
        self._require_text(self.session_id, "session ID")

        if not isinstance(self.allowed, bool):
            raise ExecutionPolicyEnforcementError(
                "Cannot build an execution policy decision with a non-bool allowed."
            )

        if not isinstance(self.evaluated_at, datetime):
            raise ExecutionPolicyEnforcementError(
                "Cannot build an execution policy decision with a non-datetime evaluated_at."
            )

        if self.violations is None:
            raise ExecutionPolicyEnforcementError(
                "Cannot build an execution policy decision with a None violations."
            )

        violations_list = list(self.violations)

        for violation in violations_list:
            if not isinstance(violation, str) or not violation.strip():
                raise ExecutionPolicyEnforcementError(
                    "Cannot build an execution policy decision with a blank violation."
                )

        object.__setattr__(self, "violations", tuple(violations_list))

        if self.allowed and violations_list:
            raise ExecutionPolicyEnforcementError(
                "Cannot build an execution policy decision that is allowed but has violations."
            )

        if not self.allowed and not violations_list:
            raise ExecutionPolicyEnforcementError(
                "Cannot build an execution policy decision that is not allowed but has no violations."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyEnforcementError(
                f"Cannot build an execution policy decision with an empty or blank {field_name}."
            )
