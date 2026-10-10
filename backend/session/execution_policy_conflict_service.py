from dataclasses import (
    replace,
)

from itertools import (
    combinations,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_policy_conflict import (
    STATUS_RESOLVED,
    STATUS_UNRESOLVED,
    ExecutionPolicyConflict,
)

from .execution_policy_conflict_error import (
    ExecutionPolicyConflictError,
)

NEGATION_PREFIX = "!"


class ExecutionPolicyConflictService:
    """
    Detects contradictory rules among policies before execution
    begins, using an existing execution policy registry as the
    source of truth for each policy's current rules. Policy
    precedence and evaluation, built by earlier commits, are assumed
    to already exist and are unaffected by this service: conflict
    detection happens independently of, and prior to, evaluating a
    session or resolving precedence between policies.

    A rule is a plain string, e.g. "delete", asserting that the
    rule's action is permitted. A policy may also carry the same
    rule negated, prefixed with "!", e.g. "!delete", asserting that
    the action must not be permitted. Two policies contradict each
    other whenever one asserts a rule and the other asserts its
    negation.

    Behavior:
    - detect() finds every contradictory rule among every pair of
      the given policies, never just the first, and records a new
      unresolved conflict for each
    - resolve() requires a non-blank resolution; a conflict can
      never be marked resolved without one
    - unresolved() lists exactly the conflicts a caller must resolve
      before letting execution proceed for a scope
    - clear() forgets which conflicts are tracked against a scope,
      but never rewrites a conflict's own history
    - history() lists every version of a conflict, including the
      version resolve() produced

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_policy_service):
        """
        Args:
            execution_policy_service: The registry used to resolve a
                policy_id to its current ExecutionPolicy, so detect()
                can compare rule sets. Any object exposing
                `get(policy_id)` is accepted
        """

        self._execution_policy_service = execution_policy_service
        self._conflicts_by_id = {}
        self._history_by_id = {}
        self._conflict_ids_by_scope = {}
        self._lock = RLock()

    def detect(self, policy_ids, scope_id: str = None) -> list:
        """
        Compare every pair of the given policies' rules and record a
        new unresolved conflict for each contradictory rule found.

        Args:
            policy_ids: The policies to compare, at least two
            scope_id: If given, every conflict found is also tracked
                against this scope, for later lookup via
                unresolved() and clear()

        Raises:
            ExecutionPolicyError: If any policy_id is unknown
        """

        with self._lock:
            policies_by_id = {
                policy_id: self._execution_policy_service.get(policy_id) for policy_id in dict.fromkeys(policy_ids)
            }

            found = []

            for first, second in combinations(policies_by_id, 2):
                for rule in self._contradictions(policies_by_id[first], policies_by_id[second]):
                    conflict = ExecutionPolicyConflict(
                        conflict_id=str(uuid4()),
                        policy_ids=(first, second),
                        rule=rule,
                    )

                    self._conflicts_by_id[conflict.conflict_id] = conflict
                    self._history_by_id[conflict.conflict_id] = [conflict]

                    if scope_id is not None:
                        self._conflict_ids_by_scope.setdefault(scope_id, []).append(conflict.conflict_id)

                    found.append(conflict)

            return found

    def resolve(self, conflict_id: str, resolution: str) -> ExecutionPolicyConflict:
        """
        Explicitly resolve a recorded conflict.

        Raises:
            ExecutionPolicyConflictError: If conflict_id is None or
                blank, no conflict is recorded under it, or
                resolution is None or blank
        """

        self._validate_text(conflict_id, "conflict ID")
        self._validate_text(resolution, "resolution")

        with self._lock:
            conflict = self._resolve_conflict(conflict_id)

            updated = replace(conflict, resolution=resolution, status=STATUS_RESOLVED)
            self._conflicts_by_id[conflict_id] = updated
            self._history_by_id[conflict_id].append(updated)

            return updated

    def unresolved(self, scope_id: str) -> list:
        """
        List every conflict tracked against a scope that has not yet
        been explicitly resolved; a non-empty result blocks execution
        for the scope.

        Raises:
            ExecutionPolicyConflictError: If scope_id is None or
                blank
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            return [
                self._conflicts_by_id[conflict_id]
                for conflict_id in self._conflict_ids_by_scope.get(scope_id, [])
                if self._conflicts_by_id[conflict_id].status == STATUS_UNRESOLVED
            ]

    def clear(self, scope_id: str) -> list:
        """
        Stop tracking every conflict recorded against a scope. Each
        conflict's own record and history are preserved; only the
        scope's tracking of them is forgotten.

        Raises:
            ExecutionPolicyConflictError: If scope_id is None or
                blank
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            conflict_ids = self._conflict_ids_by_scope.pop(scope_id, [])

            return [self._conflicts_by_id[conflict_id] for conflict_id in conflict_ids]

    def history(self, conflict_id: str) -> list:
        """
        List every version of a conflict, oldest first, including
        the version resolve() produced.

        Raises:
            ExecutionPolicyConflictError: If conflict_id is None or
                blank, or no conflict is recorded under it
        """

        self._validate_text(conflict_id, "conflict ID")

        with self._lock:
            self._resolve_conflict(conflict_id)

            return list(self._history_by_id[conflict_id])

    @staticmethod
    def _contradictions(first_policy, second_policy) -> list:
        first_positive, first_negative = ExecutionPolicyConflictService._assertions(first_policy.rules)
        second_positive, second_negative = ExecutionPolicyConflictService._assertions(second_policy.rules)

        contradictory = (first_positive & second_negative) | (second_positive & first_negative)

        return sorted(contradictory)

    @staticmethod
    def _assertions(rules) -> tuple:
        positive = {rule for rule in rules if not rule.startswith(NEGATION_PREFIX)}
        negative = {rule[len(NEGATION_PREFIX) :] for rule in rules if rule.startswith(NEGATION_PREFIX)}

        return positive, negative

    def _resolve_conflict(self, conflict_id: str) -> ExecutionPolicyConflict:
        conflict = self._conflicts_by_id.get(conflict_id)

        if conflict is None:
            raise ExecutionPolicyConflictError(f"No conflict is recorded under conflict ID {conflict_id!r}.")

        return conflict

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyConflictError(f"Cannot use an empty or blank {field_name}.")
