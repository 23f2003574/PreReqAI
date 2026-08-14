from threading import (
    RLock,
)

from .execution_policy_risk_error import (
    ExecutionPolicyRiskError,
)

from .execution_policy_risk_score import (
    MAX_SCORE,
    ExecutionPolicyRiskScore,
    level_for_score,
)

VIOLATION_WEIGHT = 10

UNRESOLVED_CONFLICT_WEIGHT = 25

EXPIRED_EXCEPTION_WEIGHT = 15

DENIED_ENFORCEMENT_WEIGHT = 20


class ExecutionPolicyRiskService:
    """
    Quantifies a session's execution policy risk from its recorded
    violations, unresolved conflicts, expired exceptions, and denied
    enforcement history, using an existing execution policy
    evaluation service, conflict service, exception service, and
    audit service as the sources of truth for each.

    The service's responsibility is scoring only. It never mutates
    any of the services it reads from: every method here is a pure,
    deterministic function of what those services already have on
    record for a session, so the same underlying state always
    produces the same score.

    Factors and their weight toward score, capped at MAX_SCORE:
    - violations: every violation across the session's recorded
      evaluation history, VIOLATION_WEIGHT each
    - unresolved_conflicts: every conflict the conflict service still
      considers unresolved for the session, UNRESOLVED_CONFLICT_WEIGHT
      each
    - expired_exceptions: every exception scoped to the session that
      has expired, EXPIRED_EXCEPTION_WEIGHT each
    - denied_enforcement_events: every "enforcement" audit event
      recorded for the session with a "denied" decision,
      DENIED_ENFORCEMENT_WEIGHT each

    Behavior:
    - calculate() records a new ExecutionPolicyRiskScore on every
      call, so a session's score history grows over repeated calls
    - factor_breakdown() and level() compute the same result as
      calculate() but are pure reads: neither records anything

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        execution_policy_evaluation_service,
        execution_policy_conflict_service,
        execution_policy_exception_service,
        execution_policy_audit_service,
    ):
        """
        Args:
            execution_policy_evaluation_service: Read via
                `history(session_id)` for the session's recorded
                evaluations and their violations
            execution_policy_conflict_service: Read via
                `unresolved(session_id)` for the session's unresolved
                conflicts
            execution_policy_exception_service: Read via `expired()`,
                filtered to exceptions whose `.scope_id` is the
                session
            execution_policy_audit_service: Read via
                `history(session_id)` for the session's recorded
                enforcement decisions
        """

        self._execution_policy_evaluation_service = execution_policy_evaluation_service
        self._execution_policy_conflict_service = execution_policy_conflict_service
        self._execution_policy_exception_service = execution_policy_exception_service
        self._execution_policy_audit_service = execution_policy_audit_service
        self._scores_by_session = {}
        self._lock = RLock()

    def calculate(self, session_id: str) -> ExecutionPolicyRiskScore:
        """
        Calculate and record a session's current risk score.

        Raises:
            ExecutionPolicyRiskError: If session_id is None or blank
        """

        self._validate_text(session_id, "session ID")

        with self._lock:
            factors = self._factors(session_id)
            score = self._score(factors)

            risk_score = ExecutionPolicyRiskScore(
                session_id=session_id,
                score=score,
                level=level_for_score(score),
                factors=factors,
            )

            self._scores_by_session.setdefault(session_id, []).append(risk_score)

            return risk_score

    def factor_breakdown(self, session_id: str) -> dict:
        """
        Compute the current factor breakdown for a session, without
        recording anything.

        Raises:
            ExecutionPolicyRiskError: If session_id is None or blank
        """

        self._validate_text(session_id, "session ID")

        with self._lock:
            return self._factors(session_id)

    def level(self, session_id: str) -> str:
        """
        Compute the current risk level for a session, without
        recording anything.

        Raises:
            ExecutionPolicyRiskError: If session_id is None or blank
        """

        self._validate_text(session_id, "session ID")

        with self._lock:
            return level_for_score(self._score(self._factors(session_id)))

    def history(self, session_id: str) -> list:
        """
        List every score recorded for a session by calculate(), in
        the order it was called.

        Raises:
            ExecutionPolicyRiskError: If session_id is None or blank
        """

        self._validate_text(session_id, "session ID")

        with self._lock:
            return list(self._scores_by_session.get(session_id, []))

    def _factors(self, session_id: str) -> dict:
        violations = sum(
            len(evaluation.violations)
            for evaluation in self._execution_policy_evaluation_service.history(session_id)
        )

        unresolved_conflicts = len(self._execution_policy_conflict_service.unresolved(session_id))

        expired_exceptions = len(
            [
                exception
                for exception in self._execution_policy_exception_service.expired()
                if exception.scope_id == session_id
            ]
        )

        denied_enforcement_events = len(
            [
                event
                for event in self._execution_policy_audit_service.history(session_id)
                if event.event_type == "enforcement" and event.decision == "denied"
            ]
        )

        return {
            "violations": violations,
            "unresolved_conflicts": unresolved_conflicts,
            "expired_exceptions": expired_exceptions,
            "denied_enforcement_events": denied_enforcement_events,
        }

    @staticmethod
    def _score(factors: dict) -> int:
        raw = (
            factors["violations"] * VIOLATION_WEIGHT
            + factors["unresolved_conflicts"] * UNRESOLVED_CONFLICT_WEIGHT
            + factors["expired_exceptions"] * EXPIRED_EXCEPTION_WEIGHT
            + factors["denied_enforcement_events"] * DENIED_ENFORCEMENT_WEIGHT
        )

        return min(raw, MAX_SCORE)

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyRiskError(f"Cannot use an empty or blank {field_name}.")
