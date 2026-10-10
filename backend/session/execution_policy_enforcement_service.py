from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_policy_decision import (
    ExecutionPolicyDecision,
)

from .execution_policy_enforcement_error import (
    ExecutionPolicyEnforcementError,
)

UNPERMITTED_ACTION_PREFIX = "unpermitted_action:"


class ExecutionPolicyEnforcementService:
    """
    Enforces every policy resolved for an execution session
    immediately before execution dispatch, using an existing
    execution policy assignment service, evaluation service,
    conflict service, and exception service as the sources of truth
    for what applies, what it evaluates to, what remains unresolved,
    and what has been explicitly excepted.

    A session's execution scope is its session_id: the same
    identifier used to resolve assignments, evaluate policies, track
    conflicts, and look up exceptions.

    Behavior:
    - authorize() denies immediately, without evaluating any policy,
      if the session has any unresolved conflict
    - Otherwise, every policy resolved for the session is evaluated,
      and every violation is kept unless an active exception exists
      for that policy_id, session_id, and rule
    - Violations are always produced in a fixed, sorted order, so
      authorize() is deterministic for the same underlying state
    - deny() records an explicit denial immediately, without
      consulting assignments, evaluation, conflicts, or exceptions
    - Every call to authorize() or deny() records a new
      ExecutionPolicyDecision; decision() and history() never
      recompute one

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        execution_policy_assignment_service,
        execution_policy_evaluation_service,
        execution_policy_conflict_service,
        execution_policy_exception_service,
    ):
        """
        Args:
            execution_policy_assignment_service: Read via
                `resolve(session_id)` for the policies applicable to
                the session
            execution_policy_evaluation_service: Read via
                `evaluate(policy_id, session_id)` for each
                applicable policy's violations
            execution_policy_conflict_service: Read via
                `unresolved(session_id)` to check whether the session
                is blocked outright
            execution_policy_exception_service: Read via
                `active(session_id)` for the exceptions that exempt
                specific violations
        """

        self._execution_policy_assignment_service = execution_policy_assignment_service
        self._execution_policy_evaluation_service = execution_policy_evaluation_service
        self._execution_policy_conflict_service = execution_policy_conflict_service
        self._execution_policy_exception_service = execution_policy_exception_service
        self._decisions_by_id = {}
        self._decision_ids_by_session = {}
        self._lock = RLock()

    def authorize(self, session_id: str) -> ExecutionPolicyDecision:
        """
        Evaluate every policy applicable to a session, apply active
        exceptions, and record the final decision.

        Raises:
            ExecutionPolicyEnforcementError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            conflicts = self._execution_policy_conflict_service.unresolved(session_id)

            if conflicts:
                violations = tuple(
                    sorted(f"unresolved_conflict:{conflict.conflict_id}" for conflict in conflicts)
                )

                return self._record(session_id, allowed=False, violations=violations)

            exempted_rules_by_policy = {}

            for exception in self._execution_policy_exception_service.active(session_id):
                exempted_rules_by_policy.setdefault(exception.policy_id, set()).add(exception.rule)

            violations = []

            for policy in self._execution_policy_assignment_service.resolve(session_id):
                evaluation = self._execution_policy_evaluation_service.evaluate(policy.policy_id, session_id)
                exempted_rules = exempted_rules_by_policy.get(policy.policy_id, set())

                for violation in evaluation.violations:
                    if self._excepted_rule(violation) in exempted_rules:
                        continue

                    violations.append(f"{policy.policy_id}:{violation}")

            violations = tuple(sorted(violations))

            return self._record(session_id, allowed=not violations, violations=violations)

    def deny(self, session_id: str) -> ExecutionPolicyDecision:
        """
        Record an explicit denial for a session, without consulting
        assignments, evaluation, conflicts, or exceptions.

        Raises:
            ExecutionPolicyEnforcementError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return self._record(session_id, allowed=False, violations=("explicit_denial",))

    def decision(self, session_id: str) -> ExecutionPolicyDecision:
        """
        Look up the most recently recorded decision for a session.

        Raises:
            ExecutionPolicyEnforcementError: If session_id is None or
                blank, or no decision has been recorded for it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            decision_ids = self._decision_ids_by_session.get(session_id)

            if not decision_ids:
                raise ExecutionPolicyEnforcementError(f"No decision has been recorded for session ID {session_id!r}.")

            return self._decisions_by_id[decision_ids[-1]]

    def history(self, session_id: str) -> list:
        """
        List every decision recorded for a session, in the order
        authorize() or deny() produced them.

        Raises:
            ExecutionPolicyEnforcementError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return [
                self._decisions_by_id[decision_id]
                for decision_id in self._decision_ids_by_session.get(session_id, [])
            ]

    def _record(self, session_id: str, allowed: bool, violations: tuple) -> ExecutionPolicyDecision:
        decision = ExecutionPolicyDecision(
            decision_id=str(uuid4()),
            session_id=session_id,
            allowed=allowed,
            violations=violations,
            evaluated_at=datetime.now(timezone.utc),
        )

        self._decisions_by_id[decision.decision_id] = decision
        self._decision_ids_by_session.setdefault(session_id, []).append(decision.decision_id)

        return decision

    @staticmethod
    def _excepted_rule(violation: str):
        if violation.startswith(UNPERMITTED_ACTION_PREFIX):
            return violation[len(UNPERMITTED_ACTION_PREFIX) :]

        return None

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyEnforcementError(f"Cannot use an empty or blank {field_name}.")
