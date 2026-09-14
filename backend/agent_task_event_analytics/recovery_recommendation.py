from .failure_classification import LLMAgentTaskEventFailureClassifier
from .failure_recovery_planning import LLMAgentTaskEventFailureRecoveryPlanner
from .models import (
    MINIMUM_CONFIDENT_SAMPLE_SIZE,
    RECOVERY_ACTION_NONE,
    RECOVERY_ACTION_UNRESOLVED,
    RECOVERY_OUTCOME_SUCCESS,
    AgentTaskRecoveryRecommendation,
)
from .recovery_effectiveness import LLMAgentTaskRecoveryEffectivenessService


class InvalidAgentTaskRecoveryRecommendationError(ValueError):
    """Raised when recommend() is given invalid arguments."""


class LLMAgentTaskRecoveryRecommendationService:
    """Turns Commit #7's own effectiveness data into one actionable
    recommendation for the task's *current* failure -- a decision layer,
    never another executor (Rule: "Never execute the recommendation") and
    never a second strategy/recommendation framework (Rule): every input
    is read from an existing service's own already-computed result, and
    the only new computation here is a small, explainable confidence
    formula (see MINIMUM_CONFIDENT_SAMPLE_SIZE's own docstring) -- nothing
    is queried, replayed, or classified a second, competing way.

    recommend() never decides *which* action is feasible -- that stays
    entirely Commit #3's own LLMAgentTaskEventFailureRecoveryPlanner.plan()
    (Rule: "Reuse existing failure classification/planning semantics"; "Do
    not invent actions"), which already folds in retry/execution limits and
    current task/dependency/readiness state through its own existing
    collaborators. This service only ever asks: given that Commit #3
    already recommends action X for the current failure, how much should a
    caller actually trust it, based on how X has performed for this exact
    task and this exact failure category before?

    Category-scoped evidence (the one genuinely new idea here): a past
    attempt only counts as evidence for the current recommendation when
    its own originating failure shared the *same* failure_category Commit
    #2 assigned the current one -- an action's track record against a
    different kind of failure is not treated as proof it will work here
    too. This requires an optional failure_classifier collaborator to look
    up each past attempt's own category; without one, this service
    degrades to the action's unscoped history rather than refusing to
    answer (the same "optional collaborator; less to work with when
    omitted, never a hard failure" shape this project's services already
    use throughout).

    Confidence is always 0.0, and the action itself is left exactly as
    Commit #3 named it, whenever there is no supporting evidence at all
    (Rule: "Low/no evidence must produce low confidence or an explicit
    no-recommendation result") -- when Commit #3's own plan itself has
    nothing to recommend (RECOVERY_ACTION_NONE) or could not resolve one
    (RECOVERY_ACTION_UNRESOLVED), that exact action/reason is passed
    through unchanged as an explicit no-recommendation result, with no
    historical lookup attempted at all (there is nothing to look up
    evidence for).

    Deterministic (Rule): every collaborator here is already deterministic
    over its own fixed input, and the confidence formula is a pure
    function of counts already returned by Commit #7 -- calling recommend()
    twice in a row with nothing changed in between always returns an
    identical result.
    """

    def __init__(
        self,
        planner: LLMAgentTaskEventFailureRecoveryPlanner = None,
        effectiveness_service: LLMAgentTaskRecoveryEffectivenessService = None,
        classifier: LLMAgentTaskEventFailureClassifier = None,
    ):
        self._planner = planner if planner is not None else LLMAgentTaskEventFailureRecoveryPlanner()
        self._effectiveness_service = (
            effectiveness_service if effectiveness_service is not None else LLMAgentTaskRecoveryEffectivenessService()
        )
        self._classifier = classifier

    def recommend(self, task_id: str) -> AgentTaskRecoveryRecommendation:
        """Recommend one action for task_id's current failure, with a
        confidence figure grounded in this exact task's own recovery
        history for this exact failure category.

        Raises:
            InvalidAgentTaskRecoveryRecommendationError: If task_id is not
                a non-empty string
        """
        self._require_text(task_id)

        plan = self._planner.plan(task_id)
        action = plan.recommended_action

        if action in (RECOVERY_ACTION_NONE, RECOVERY_ACTION_UNRESOLVED):
            return AgentTaskRecoveryRecommendation(
                task_id=task_id,
                recommended_action=action,
                confidence=0.0,
                reason=plan.reason,
                supporting_recovery_ids=(),
                blocking_conditions=plan.blocking_conditions,
            )

        effectiveness = self._effectiveness_service.analyze(task_id)
        relevant_attempts = self._category_scoped_attempts(task_id, effectiveness.attempts, plan.failure_category)
        matching = [
            outcome for outcome in relevant_attempts if (outcome.executed_action or outcome.planned_action) == action
        ]
        successes = [outcome for outcome in matching if outcome.status == RECOVERY_OUTCOME_SUCCESS]

        if not matching:
            confidence = 0.0
            historical_note = (
                f"no prior recovery attempts using {action!r} for a {plan.failure_category!r} "
                "failure are on record for this task"
            )
        else:
            raw_rate = len(successes) / len(matching)
            confidence = raw_rate * min(1.0, len(matching) / MINIMUM_CONFIDENT_SAMPLE_SIZE)
            historical_note = (
                f"{action!r} succeeded in {len(successes)} of {len(matching)} prior attempt(s) for a "
                f"{plan.failure_category!r} failure (historical success rate {raw_rate:.0%})"
            )

        return AgentTaskRecoveryRecommendation(
            task_id=task_id,
            recommended_action=action,
            confidence=confidence,
            reason=f"{plan.reason}; {historical_note}",
            supporting_recovery_ids=tuple(outcome.recovery_id for outcome in successes),
            blocking_conditions=plan.blocking_conditions,
        )

    def _category_scoped_attempts(self, task_id: str, attempts, failure_category) -> list:
        if self._classifier is None or failure_category is None:
            return list(attempts)

        classification = self._classifier.classify(task_id)
        category_by_failure_event_id = {failure.event_id: failure.category for failure in classification.failures}

        return [
            outcome
            for outcome in attempts
            if category_by_failure_event_id.get(outcome.source_failure_event_id) == failure_category
        ]

    @staticmethod
    def _require_text(task_id) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryRecommendationError("task_id is required and must be a non-empty string")
