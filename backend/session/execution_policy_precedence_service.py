from threading import (
    RLock,
)

from .execution_policy_precedence import (
    ExecutionPolicyPrecedence,
)

from .execution_policy_precedence_error import (
    ExecutionPolicyPrecedenceError,
)


class ExecutionPolicyPrecedenceService:
    """
    Resolves a deterministic order among policies that jointly
    govern the same execution, using explicit precedence rules where
    they exist and falling back to each policy's existing numeric
    priority order otherwise, using an existing execution policy
    assignment service as the source of truth for a scope's
    assigned policies and their numeric priority order.

    The service's responsibility is ordering only. It never mutates
    a policy or an assignment; it only records its own precedence
    rules and computes orderings from them.

    Behavior:
    - set() records that one policy outranks another, and rejects a
      rule that would make a policy outrank itself, directly or
      transitively
    - resolve() takes policy_ids already in their numeric-priority
      order and reorders them so every recorded rule is honored,
      while leaving any pair with no recorded rule between them,
      direct or transitive, in their original relative order
    - order() resolves the policies assigned to a scope, using an
      existing execution policy assignment service to establish
      their numeric-priority baseline before applying precedence
      rules
    - conflicts() reports every pair in a list with no recorded rule
      between them, direct or transitive, so a caller can see which
      pairs are being ordered by numeric fallback alone

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_policy_assignment_service):
        """
        Args:
            execution_policy_assignment_service: The service used by
                order() to resolve a scope_id to its effective
                policies in numeric-priority order. Any object
                exposing `resolve(scope_id)`, returning an iterable
                of objects with a `.policy_id`, is accepted
        """

        self._execution_policy_assignment_service = execution_policy_assignment_service
        self._outranks = {}
        self._next_priority = 0
        self._lock = RLock()

    def set(self, policy_id: str, higher_than: str) -> ExecutionPolicyPrecedence:
        """
        Record that policy_id outranks higher_than.

        Raises:
            ExecutionPolicyPrecedenceError: If policy_id or
                higher_than is invalid, policy_id equals higher_than,
                or the rule would create a precedence cycle
        """

        with self._lock:
            if self._reachable(higher_than, policy_id):
                raise ExecutionPolicyPrecedenceError(
                    f"Cannot record that {policy_id!r} outranks {higher_than!r}: "
                    f"{higher_than!r} already outranks {policy_id!r}, directly or transitively."
                )

            rule = ExecutionPolicyPrecedence(
                policy_id=policy_id,
                higher_than=higher_than,
                priority=self._next_priority,
            )

            self._next_priority += 1
            self._outranks.setdefault(policy_id, set()).add(higher_than)

            return rule

    def resolve(self, policy_ids) -> list:
        """
        Reorder policy_ids, already in their numeric-priority order,
        so every recorded rule between two of them is honored,
        leaving unrelated pairs in their original relative order.
        """

        with self._lock:
            ids = list(policy_ids)
            id_set = set(ids)
            position = {policy_id: index for index, policy_id in enumerate(ids)}

            successors = {
                policy_id: [
                    higher_than
                    for higher_than in self._outranks.get(policy_id, ())
                    if higher_than in id_set
                ]
                for policy_id in ids
            }

            in_degree = {policy_id: 0 for policy_id in ids}

            for policy_id in ids:
                for higher_than in successors[policy_id]:
                    in_degree[higher_than] += 1

            remaining = set(ids)
            result = []

            while remaining:
                ready = [policy_id for policy_id in remaining if in_degree[policy_id] == 0]
                next_id = min(ready, key=lambda policy_id: position[policy_id])

                result.append(next_id)
                remaining.remove(next_id)

                for higher_than in successors[next_id]:
                    if higher_than in remaining:
                        in_degree[higher_than] -= 1

            return result

    def order(self, scope_id: str) -> list:
        """
        Resolve the deterministic order of the policies assigned to
        a scope, honoring recorded precedence rules over the scope's
        numeric-priority assignment order.

        Raises:
            ExecutionPolicyPrecedenceError: If scope_id is None or
                blank
        """

        if scope_id is None or not scope_id.strip():
            raise ExecutionPolicyPrecedenceError("Cannot use an empty or blank scope ID.")

        with self._lock:
            baseline = [policy.policy_id for policy in self._execution_policy_assignment_service.resolve(scope_id)]

            return self.resolve(baseline)

    def conflicts(self, policy_ids) -> list:
        """
        List every pair in policy_ids with no recorded rule between
        them, direct or transitive, in the order the pairs appear.
        """

        with self._lock:
            ids = list(policy_ids)
            found = []

            for i, first in enumerate(ids):
                for second in ids[i + 1 :]:
                    if not self._reachable(first, second) and not self._reachable(second, first):
                        found.append((first, second))

            return found

    def _reachable(self, start: str, target: str) -> bool:
        if start == target:
            return True

        visited = {start}
        queue = [start]

        while queue:
            current = queue.pop()

            for neighbor in self._outranks.get(current, ()):
                if neighbor == target:
                    return True

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return False
