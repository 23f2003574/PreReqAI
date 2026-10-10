from threading import (
    RLock,
)

from uuid import uuid4

from .execution_policy_assignment import (
    SCOPE_TYPES_BY_SPECIFICITY,
    ExecutionPolicyAssignment,
)

from .execution_policy_assignment_error import (
    ExecutionPolicyAssignmentError,
)


class ExecutionPolicyAssignmentService:
    """
    Assigns registered execution policies to the scopes they govern,
    using an existing execution policy registry as the source of
    truth for whether an assigned policy is currently enabled.

    Scopes nest, most specific first: a session scope is nested
    inside a workspace scope, which is nested inside an
    execution_scope scope. A given scope_id may have assignments
    recorded directly against it under any of these scope_types;
    resolve() combines all of them, as if the same scope_id denotes
    the session, its workspace, and its execution scope at once.

    Behavior:
    - assign() rejects a second assignment of the same policy_id to
      the same (scope_type, scope_id)
    - policies() lists only the enabled policies assigned directly
      to a single (scope_type, scope_id), highest priority first
    - resolve() lists the enabled policies effective for a scope_id
      across every scope_type, most specific first; if the same
      policy is assigned at more than one level, only its
      highest-priority assignment counts
    - Ties are broken deterministically: first by priority (higher
      wins), then by scope specificity (session over workspace over
      execution_scope), then by assignment order

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_policy_service):
        """
        Args:
            execution_policy_service: The registry used to resolve a
                policy_id to its current ExecutionPolicy, so that
                assign() can confirm the policy exists and
                policies()/resolve() can filter out disabled
                policies. Any object exposing `get(policy_id)` is
                accepted
        """

        self._execution_policy_service = execution_policy_service
        self._assignments_by_id = {}
        self._assignment_ids_by_scope = {}
        self._lock = RLock()

    def assign(self, policy_id: str, scope_type: str, scope_id: str, priority: int = 0) -> ExecutionPolicyAssignment:
        """
        Assign a policy to a scope.

        Raises:
            ExecutionPolicyAssignmentError: If policy_id, scope_type,
                or scope_id is invalid, or the policy is already
                assigned to this scope
            ExecutionPolicyError: If no policy is registered under
                policy_id
        """

        self._execution_policy_service.get(policy_id)

        with self._lock:
            scope_key = (scope_type, scope_id)

            for assignment_id in self._assignment_ids_by_scope.get(scope_key, []):
                if self._assignments_by_id[assignment_id].policy_id == policy_id:
                    raise ExecutionPolicyAssignmentError(
                        f"Policy ID {policy_id!r} is already assigned to scope {scope_key!r}."
                    )

            assignment = ExecutionPolicyAssignment(
                assignment_id=str(uuid4()),
                policy_id=policy_id,
                scope_type=scope_type,
                scope_id=scope_id,
                priority=priority,
            )

            self._assignments_by_id[assignment.assignment_id] = assignment
            self._assignment_ids_by_scope.setdefault(scope_key, []).append(assignment.assignment_id)

            return assignment

    def remove(self, assignment_id: str) -> ExecutionPolicyAssignment:
        """
        Remove a recorded assignment.

        Raises:
            ExecutionPolicyAssignmentError: If assignment_id is None
                or blank, or no assignment is recorded under it
        """

        self._validate_text(assignment_id, "assignment ID")

        with self._lock:
            assignment = self._resolve(assignment_id)

            del self._assignments_by_id[assignment_id]

            scope_key = (assignment.scope_type, assignment.scope_id)
            self._assignment_ids_by_scope[scope_key].remove(assignment_id)

            return assignment

    def policies(self, scope_type: str, scope_id: str) -> list:
        """
        List the enabled policies assigned directly to a scope,
        highest priority first.

        Raises:
            ExecutionPolicyAssignmentError: If scope_type is not a
                known scope type, or scope_id is None or blank
        """

        self._validate_scope_type(scope_type)
        self._validate_text(scope_id, "scope ID")

        with self._lock:
            ranked = self._ranked_candidates(scope_type, scope_id, scope_rank=0)

            return [policy for _rank, policy in sorted(ranked, key=lambda item: item[0])]

    def resolve(self, scope_id: str) -> list:
        """
        List the enabled policies effective for a scope_id across
        every scope_type it may be assigned under, most specific
        first. If a policy is assigned at more than one level, only
        its highest-priority assignment is kept.

        Raises:
            ExecutionPolicyAssignmentError: If scope_id is None or
                blank
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            best_by_policy = {}

            for scope_rank, scope_type in enumerate(SCOPE_TYPES_BY_SPECIFICITY):
                for rank, policy in self._ranked_candidates(scope_type, scope_id, scope_rank):
                    existing = best_by_policy.get(policy.policy_id)

                    if existing is None or rank < existing[0]:
                        best_by_policy[policy.policy_id] = (rank, policy)

            return [policy for _rank, policy in sorted(best_by_policy.values(), key=lambda item: item[0])]

    def _ranked_candidates(self, scope_type: str, scope_id: str, scope_rank: int) -> list:
        candidates = []

        for index, assignment_id in enumerate(self._assignment_ids_by_scope.get((scope_type, scope_id), [])):
            assignment = self._assignments_by_id[assignment_id]
            policy = self._execution_policy_service.get(assignment.policy_id)

            if not policy.enabled:
                continue

            candidates.append(((-assignment.priority, scope_rank, index), policy))

        return candidates

    def _resolve(self, assignment_id: str) -> ExecutionPolicyAssignment:
        assignment = self._assignments_by_id.get(assignment_id)

        if assignment is None:
            raise ExecutionPolicyAssignmentError(f"No assignment is recorded under assignment ID {assignment_id!r}.")

        return assignment

    @staticmethod
    def _validate_scope_type(scope_type: str) -> None:
        if scope_type not in SCOPE_TYPES_BY_SPECIFICITY:
            raise ExecutionPolicyAssignmentError(f"Unknown scope_type: {scope_type!r}.")

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyAssignmentError(f"Cannot use an empty or blank {field_name}.")
