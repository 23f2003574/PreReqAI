from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_policy_evaluation_error import (
    ExecutionPolicyEvaluationError,
)


@dataclass(frozen=True)
class ExecutionPolicyEvaluation:
    """
    Immutable record of evaluating a single policy against a single
    execution session at a point in time.

    The evaluation is a value object only. It performs no evaluation
    of its own; comparing a policy's rules against a session and
    producing this record is the responsibility of an execution
    policy evaluation service.

    Attributes:
        evaluation_id: The evaluation's unique identifier
        policy_id: The identifier of the policy that was evaluated
        session_id: The identifier of the execution session the
            policy was evaluated against
        allowed: Whether the session satisfied the policy, i.e.
            violations is empty
        violations: Every rule the session violated, in the order
            they were found. Empty if and only if allowed is True
        evaluated_at: When this evaluation occurred
    """

    evaluation_id: str

    policy_id: str

    session_id: str

    allowed: bool

    violations: tuple

    evaluated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.evaluation_id, "evaluation ID")
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.session_id, "session ID")

        if not isinstance(self.allowed, bool):
            raise ExecutionPolicyEvaluationError(
                "Cannot build an execution policy evaluation with a non-bool allowed."
            )

        if not isinstance(self.evaluated_at, datetime):
            raise ExecutionPolicyEvaluationError(
                "Cannot build an execution policy evaluation with a non-datetime evaluated_at."
            )

        if self.violations is None:
            raise ExecutionPolicyEvaluationError(
                "Cannot build an execution policy evaluation with a None violations."
            )

        violations_list = list(self.violations)

        for violation in violations_list:
            if not isinstance(violation, str) or not violation.strip():
                raise ExecutionPolicyEvaluationError(
                    "Cannot build an execution policy evaluation with a blank violation."
                )

        object.__setattr__(self, "violations", tuple(violations_list))

        if self.allowed and violations_list:
            raise ExecutionPolicyEvaluationError(
                "Cannot build an execution policy evaluation that is allowed but has violations."
            )

        if not self.allowed and not violations_list:
            raise ExecutionPolicyEvaluationError(
                "Cannot build an execution policy evaluation that is not allowed but has no violations."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyEvaluationError(
                f"Cannot build an execution policy evaluation with an empty or blank {field_name}."
            )
