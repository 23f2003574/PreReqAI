from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_policy_error import (
    ExecutionPolicyError,
)


@dataclass(frozen=True)
class ExecutionPolicy:
    """
    Immutable declaration of what an execution session is permitted
    to do.

    The policy is a value object only. It performs no evaluation of
    its own; registering, updating, disabling, and evaluating
    policies is the responsibility of an execution policy service.

    Attributes:
        policy_id: The policy's unique identifier
        name: A human-readable name for the policy
        rules: The non-empty set of rules this policy grants
        enabled: Whether this policy currently applies; a disabled
            policy can never be evaluated
        created_at: When this version of the policy was created
    """

    policy_id: str

    name: str

    rules: frozenset

    enabled: bool = True

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.name, "name")

        if not isinstance(self.enabled, bool):
            raise ExecutionPolicyError(
                "Cannot build an execution policy with a non-bool enabled."
            )

        if not isinstance(self.created_at, datetime):
            raise ExecutionPolicyError(
                "Cannot build an execution policy with a non-datetime created_at."
            )

        if self.rules is None:
            raise ExecutionPolicyError(
                "Cannot build an execution policy with an empty rules."
            )

        rules_list = list(self.rules)

        if not rules_list:
            raise ExecutionPolicyError(
                "Cannot build an execution policy with an empty rules."
            )

        for rule in rules_list:
            if not isinstance(rule, str) or not rule.strip():
                raise ExecutionPolicyError(
                    "Cannot build an execution policy with a blank rule."
                )

        object.__setattr__(self, "rules", frozenset(rules_list))

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyError(
                f"Cannot build an execution policy with an empty or blank {field_name}."
            )
