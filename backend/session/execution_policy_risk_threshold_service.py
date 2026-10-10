from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_policy_risk_threshold import (
    ACTION_ALLOW,
    ExecutionPolicyRiskThreshold,
)

from .execution_policy_risk_threshold_error import (
    ExecutionPolicyRiskThresholdError,
)


class ExecutionPolicyRiskThresholdService:
    """
    Turns a session's risk score, produced by an existing execution
    policy risk service, into a configurable enforcement action by
    matching it against registered thresholds.

    Behavior:
    - Among every enabled threshold whose minimum_score is at most
      the session's current score, the one with the highest
      minimum_score wins; ties are broken by registration order, so
      evaluate() is deterministic for the same underlying state
    - A session whose score matches no enabled threshold defaults to
      ACTION_ALLOW
    - Disabled thresholds are never matched, whether disabled before
      or after registration

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_policy_risk_service):
        """
        Args:
            execution_policy_risk_service: The service used to
                calculate a session's current risk score. Any object
                exposing `calculate(session_id)`, returning an object
                with a `.score`, is accepted
        """

        self._execution_policy_risk_service = execution_policy_risk_service
        self._thresholds_by_id = {}
        self._order = []
        self._lock = RLock()

    def register(self, threshold: ExecutionPolicyRiskThreshold) -> ExecutionPolicyRiskThreshold:
        """
        Register a threshold.

        Raises:
            ExecutionPolicyRiskThresholdError: If threshold is not an
                ExecutionPolicyRiskThreshold, or its threshold ID is
                already registered
        """

        if not isinstance(threshold, ExecutionPolicyRiskThreshold):
            raise ExecutionPolicyRiskThresholdError(
                "Cannot register an invalid threshold: threshold must be an ExecutionPolicyRiskThreshold."
            )

        with self._lock:
            if threshold.threshold_id in self._thresholds_by_id:
                raise ExecutionPolicyRiskThresholdError(
                    f"Threshold ID {threshold.threshold_id!r} is already registered."
                )

            self._thresholds_by_id[threshold.threshold_id] = threshold
            self._order.append(threshold.threshold_id)

            return threshold

    def evaluate(self, session_id: str) -> str:
        """
        Calculate a session's current risk score and return the
        action of the highest matching enabled threshold, or
        ACTION_ALLOW if none match.

        Raises:
            ExecutionPolicyRiskThresholdError: If session_id is None
                or blank
        """

        if session_id is None or not session_id.strip():
            raise ExecutionPolicyRiskThresholdError("Cannot use an empty or blank session ID.")

        with self._lock:
            score = self._execution_policy_risk_service.calculate(session_id).score

            candidates = [
                (index, threshold)
                for index, threshold_id in enumerate(self._order)
                for threshold in (self._thresholds_by_id[threshold_id],)
                if threshold.enabled and threshold.minimum_score <= score
            ]

            if not candidates:
                return ACTION_ALLOW

            _index, winner = max(
                candidates,
                key=lambda candidate: (candidate[1].minimum_score, -candidate[0]),
            )

            return winner.action

    def thresholds(self) -> list:
        """
        List every registered threshold, in registration order.
        """

        with self._lock:
            return [self._thresholds_by_id[threshold_id] for threshold_id in self._order]

    def disable(self, threshold_id: str) -> ExecutionPolicyRiskThreshold:
        """
        Disable a registered threshold, so it is never matched.

        Raises:
            ExecutionPolicyRiskThresholdError: If threshold_id is
                None or blank, or no threshold is registered under it
        """

        if threshold_id is None or not threshold_id.strip():
            raise ExecutionPolicyRiskThresholdError("Cannot use an empty or blank threshold ID.")

        with self._lock:
            threshold = self._thresholds_by_id.get(threshold_id)

            if threshold is None:
                raise ExecutionPolicyRiskThresholdError(
                    f"No threshold is registered under threshold ID {threshold_id!r}."
                )

            updated = replace(threshold, enabled=False)
            self._thresholds_by_id[threshold_id] = updated

            return updated
