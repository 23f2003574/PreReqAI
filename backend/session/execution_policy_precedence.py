from dataclasses import (
    dataclass,
)

from .execution_policy_precedence_error import (
    ExecutionPolicyPrecedenceError,
)


@dataclass(frozen=True)
class ExecutionPolicyPrecedence:
    """
    Immutable record of an explicit precedence rule declaring that
    one policy outranks another.

    The rule is a value object only. It performs no ordering of its
    own; recording rules, detecting cycles among them, and resolving
    a deterministic order from them is the responsibility of an
    execution policy precedence service.

    Attributes:
        policy_id: The identifier of the policy this rule declares
            to have higher precedence
        higher_than: The identifier of the policy that policy_id
            outranks. Must differ from policy_id: a policy cannot be
            declared to outrank itself
        priority: The order in which this rule was declared relative
            to every other rule, lowest first; assigned by the
            precedence service, never by a caller
    """

    policy_id: str

    higher_than: str

    priority: int

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.higher_than, "higher_than policy ID")

        if self.policy_id == self.higher_than:
            raise ExecutionPolicyPrecedenceError(
                f"Cannot build an execution policy precedence rule where policy ID {self.policy_id!r} outranks itself."
            )

        if not isinstance(self.priority, int) or isinstance(self.priority, bool) or self.priority < 0:
            raise ExecutionPolicyPrecedenceError(
                "Cannot build an execution policy precedence rule with a negative or non-int priority."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyPrecedenceError(
                f"Cannot build an execution policy precedence rule with an empty or blank {field_name}."
            )
