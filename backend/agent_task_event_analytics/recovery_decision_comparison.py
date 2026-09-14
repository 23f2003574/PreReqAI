from .models import AgentTaskRecoveryDecisionComparison
from .recovery_decision_audit import LLMAgentTaskRecoveryDecisionAuditService
from .recovery_effectiveness import LLMAgentTaskRecoveryEffectivenessService
from .recovery_history import LLMAgentTaskRecoveryHistoryService


class InvalidAgentTaskRecoveryDecisionComparisonError(ValueError):
    """Raised when compare() is given invalid arguments, or task_id/
    decision_id names no recorded decision at all."""


class LLMAgentTaskRecoveryDecisionComparisonService:
    """Compares one Commit #9 recovery decision against the recovery
    attempt that actually followed it -- never a second analytics/audit
    framework (Rule): every input is read from an existing service's own
    already-computed result (Commit #9's own
    LLMAgentTaskRecoveryDecisionAuditService, Commit #6's own
    LLMAgentTaskRecoveryHistoryService, Commit #7's own
    LLMAgentTaskRecoveryEffectivenessService); the only new logic here is
    the matching step and the small comparison it produces.

    Read-only (Rule): compare() never calls record()/emit()/execute() on
    anything, and never mutates the audit or outcome it compares (Rule:
    "Do not modify audits, recovery history, or task state").

    Matching is reference-based, never merely temporal (Rule: "Do not
    infer causality from temporal proximity alone" -- see
    AgentTaskRecoveryDecisionComparison's own docstring for the exact
    matching rule): a candidate recovery outcome must share the decision's
    own failure_event_id and have completed at or after the decision was
    made; the earliest such outcome (Commit #6's own deterministic
    ordering) is the one compared. There is deliberately no "closest in
    time" fallback that ignores the failure reference -- an outcome for a
    *different* failure is never treated as evidence about this decision,
    no matter how close in time it occurred.

    Unknown stays unknown (Rule): "no corresponding recovery" (nothing
    ever attempted for this decision's own failure) and "insufficient
    evidence" (an attempt exists, but Commit #7's own
    terminal_failure_after_recovery cannot be determined, e.g. no failure
    classifier was ever wired into the effectiveness_service supplied
    here) are kept as two distinct, honestly-reported outcomes -- neither
    is guessed at or collapsed into the other.

    Deterministic (Rule): every collaborator here is already deterministic
    over its own fixed input, and the matching/comparison logic is a pure
    function of their outputs -- calling compare() twice in a row with
    nothing changed in between always returns an identical result.
    """

    def __init__(
        self,
        audit_service: LLMAgentTaskRecoveryDecisionAuditService = None,
        history_service: LLMAgentTaskRecoveryHistoryService = None,
        effectiveness_service: LLMAgentTaskRecoveryEffectivenessService = None,
    ):
        self._audit_service = (
            audit_service if audit_service is not None else LLMAgentTaskRecoveryDecisionAuditService()
        )
        self._history_service = (
            history_service if history_service is not None else LLMAgentTaskRecoveryHistoryService()
        )
        self._effectiveness_service = (
            effectiveness_service if effectiveness_service is not None else LLMAgentTaskRecoveryEffectivenessService()
        )

    def compare(self, task_id: str, decision_id: str = None) -> AgentTaskRecoveryDecisionComparison:
        """Compare task_id's decision (the one named by decision_id, or
        its most recently recorded decision when omitted) against
        whichever recovery attempt actually followed it.

        Raises:
            InvalidAgentTaskRecoveryDecisionComparisonError: If task_id is
                not a non-empty string, decision_id is given and is not a
                non-empty string, or no matching decision is recorded at
                all
        """
        self._require_text(task_id)
        if decision_id is not None:
            self._require_text(decision_id, field_name="decision_id")

        decision = self._audit_service.get(task_id, decision_id=decision_id)
        if decision is None:
            raise InvalidAgentTaskRecoveryDecisionComparisonError(
                f"no recovery decision is recorded for task_id {task_id!r}"
                + (f" with decision_id {decision_id!r}" if decision_id is not None else "")
            )

        outcomes = self._history_service.get(task_id)
        matching_outcome = self._find_following_outcome(decision, outcomes)

        if matching_outcome is None:
            return AgentTaskRecoveryDecisionComparison(
                task_id=task_id,
                decision_id=decision.decision_id,
                recommended_action=decision.recommended_action,
                executed_action=None,
                recommendation_confidence=decision.confidence,
                outcome_status=None,
                was_followed=None,
                was_effective=None,
                comparison_reason=(
                    "no recovery attempt is recorded for this decision's own originating failure"
                ),
                recovery_id=None,
            )

        was_followed = matching_outcome.executed_action == decision.recommended_action

        was_effective = None
        effectiveness = self._effectiveness_service.analyze(task_id)
        if effectiveness.terminal_failure_after_recovery is not None:
            was_effective = not effectiveness.terminal_failure_after_recovery

        comparison_reason = self._build_reason(decision, matching_outcome, was_followed, was_effective)

        return AgentTaskRecoveryDecisionComparison(
            task_id=task_id,
            decision_id=decision.decision_id,
            recommended_action=decision.recommended_action,
            executed_action=matching_outcome.executed_action,
            recommendation_confidence=decision.confidence,
            outcome_status=matching_outcome.status,
            was_followed=was_followed,
            was_effective=was_effective,
            comparison_reason=comparison_reason,
            recovery_id=matching_outcome.recovery_id,
        )

    @staticmethod
    def _find_following_outcome(decision, outcomes):
        for outcome in outcomes:
            if outcome.source_failure_event_id != decision.failure_event_id:
                continue
            if outcome.completed_at < decision.created_at:
                continue
            return outcome  # outcomes is already oldest-to-newest, so this is the earliest qualifying one
        return None

    @staticmethod
    def _build_reason(decision, outcome, was_followed, was_effective) -> str:
        parts = []
        if was_followed:
            parts.append(f"recommended action {decision.recommended_action!r} was executed as recommended")
        else:
            parts.append(
                f"recommended action {decision.recommended_action!r} was not followed; "
                f"{outcome.executed_action!r} was executed instead"
            )
        parts.append(f"execution outcome: {outcome.status}")
        if was_effective is None:
            parts.append("insufficient evidence to judge whether the task ultimately recovered")
        elif was_effective:
            parts.append("the task did not end in a terminal failure after this recovery attempt")
        else:
            parts.append("the task ultimately ended in a terminal failure despite this recovery attempt")
        return "; ".join(parts)

    @staticmethod
    def _require_text(value, field_name: str = "task_id") -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryDecisionComparisonError(
                f"{field_name} is required and must be a non-empty string"
            )
