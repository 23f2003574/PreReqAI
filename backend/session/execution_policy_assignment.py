from dataclasses import (
    dataclass,
)

from .execution_policy_assignment_error import (
    ExecutionPolicyAssignmentError,
)

SCOPE_TYPES_BY_SPECIFICITY = (
    "session",
    "workspace",
    "execution_scope",
)


@dataclass(frozen=True)
class ExecutionPolicyAssignment:
    """
    Immutable record binding a policy to a scope it applies to.

    The assignment is a value object only. It performs no
    resolution of its own; assigning, removing, and resolving the
    policies effective for a scope is the responsibility of an
    execution policy assignment service.

    Scopes are ordered from most to least specific, most specific
    first, so that inheritance resolution has a deterministic
    fallback order: session, then workspace, then execution_scope.

    Attributes:
        assignment_id: The assignment's unique identifier
        policy_id: The identifier of the policy being assigned
        scope_type: The kind of scope the policy is assigned to, one
            of SCOPE_TYPES_BY_SPECIFICITY
        scope_id: The identifier of the scope the policy is assigned
            to
        priority: How strongly this assignment is preferred relative
            to other assignments effective for the same scope; a
            higher priority wins
    """

    assignment_id: str

    policy_id: str

    scope_type: str

    scope_id: str

    priority: int = 0

    def __post_init__(self):
        self._require_text(self.assignment_id, "assignment ID")
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.scope_id, "scope ID")

        if self.scope_type not in SCOPE_TYPES_BY_SPECIFICITY:
            raise ExecutionPolicyAssignmentError(
                f"Cannot build an execution policy assignment with an unknown scope_type: {self.scope_type!r}."
            )

        if not isinstance(self.priority, int) or isinstance(self.priority, bool):
            raise ExecutionPolicyAssignmentError(
                "Cannot build an execution policy assignment with a non-int priority."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyAssignmentError(
                f"Cannot build an execution policy assignment with an empty or blank {field_name}."
            )
