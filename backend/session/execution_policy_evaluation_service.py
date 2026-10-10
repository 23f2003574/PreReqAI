from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_policy_evaluation import (
    ExecutionPolicyEvaluation,
)

from .execution_policy_evaluation_error import (
    ExecutionPolicyEvaluationError,
)


class ExecutionPolicyEvaluationService:
    """
    Evaluates a registered execution policy against an execution
    session and records the explicit violations found, using an
    existing execution policy registry and execution session service
    as the sources of truth for policy rules and session actions.

    The service's responsibility is evaluation and bookkeeping only.
    It never mutates the policy it evaluates or the session it
    evaluates against; evaluation is read-only with respect to both.

    A policy's rules are the actions a session is permitted to
    perform. A session violates the policy for every action it
    requested that is not among the policy's rules.

    Behavior:
    - A disabled policy always fails evaluation, with a single
      "policy_disabled" violation; its rules are not otherwise
      considered
    - An enabled policy is evaluated against every action the
      session requested, never stopping at the first violation, so
      every unpermitted action is reported
    - evaluate() records a new ExecutionPolicyEvaluation on every
      call, so a session's evaluation history grows over repeated
      calls
    - violations() computes the same result as evaluate() but is a
      pure read: it never records anything
    - history() is scoped per session_id and never sees another
      session's evaluations

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_policy_service, execution_session_service):
        """
        Args:
            execution_policy_service: The registry used to resolve a
                policy_id to its current ExecutionPolicy. Any object
                exposing `get(policy_id)` is accepted
            execution_session_service: The service used to resolve a
                session_id to the actions it requested. Any object
                exposing `requested_actions(session_id)`, returning
                an iterable of strings, is accepted. It may raise
                whatever error it considers appropriate for an
                unknown session_id; that error is not caught or
                replaced by this service
        """

        self._execution_policy_service = execution_policy_service
        self._execution_session_service = execution_session_service
        self._evaluations_by_id = {}
        self._evaluation_ids_by_session = {}
        self._lock = RLock()

    def evaluate(self, policy_id: str, session_id: str) -> ExecutionPolicyEvaluation:
        """
        Evaluate a policy against a session and record the result.

        Raises:
            ExecutionPolicyEvaluationError: If policy_id or session_id
                is None or blank
        """

        self._validate_id(policy_id, "policy ID")
        self._validate_id(session_id, "session ID")

        with self._lock:
            violations = self._violations(policy_id, session_id)

            evaluation = ExecutionPolicyEvaluation(
                evaluation_id=str(uuid4()),
                policy_id=policy_id,
                session_id=session_id,
                allowed=not violations,
                violations=tuple(violations),
                evaluated_at=datetime.now(timezone.utc),
            )

            self._evaluations_by_id[evaluation.evaluation_id] = evaluation
            self._evaluation_ids_by_session.setdefault(session_id, []).append(evaluation.evaluation_id)

            return evaluation

    def violations(self, policy_id: str, session_id: str) -> list:
        """
        List every rule a session currently violates under a policy,
        without recording an evaluation.

        Raises:
            ExecutionPolicyEvaluationError: If policy_id or session_id
                is None or blank
        """

        self._validate_id(policy_id, "policy ID")
        self._validate_id(session_id, "session ID")

        with self._lock:
            return self._violations(policy_id, session_id)

    def history(self, session_id: str) -> list:
        """
        List every recorded evaluation for a session, in the order
        evaluate() was called.

        Raises:
            ExecutionPolicyEvaluationError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return [
                self._evaluations_by_id[evaluation_id]
                for evaluation_id in self._evaluation_ids_by_session.get(session_id, [])
            ]

    def _violations(self, policy_id: str, session_id: str) -> list:
        policy = self._execution_policy_service.get(policy_id)

        if not policy.enabled:
            return ["policy_disabled"]

        requested_actions = self._execution_session_service.requested_actions(session_id)

        return [
            f"unpermitted_action:{action}"
            for action in sorted(set(requested_actions))
            if action not in policy.rules
        ]

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyEvaluationError(f"Cannot use an empty or blank {field_name}.")
