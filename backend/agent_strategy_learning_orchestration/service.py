from datetime import datetime, timezone

from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_strategy_decision_audit import LEARNED, LLMAgentStrategyDecisionAuditService
from backend.agent_strategy_feedback import LLMAgentStrategyFeedbackService
from backend.agent_strategy_lifecycle import LLMAgentStrategyLifecycleEvaluator
from backend.agent_strategy_scoring import LLMAgentStrategyScorer
from backend.llm.tool_execution import RUNNING

from .models import FAILED, PROCESSED, SKIPPED, LLMAgentStrategyLearningResult


def _operation(step: str, outcome: str, detail: str) -> dict:
    return {"step": step, "outcome": outcome, "detail": detail}


class LLMAgentStrategyLearningOrchestrator:
    """Closes the strategy learning loop: execution result -> outcome
    evidence -> effectiveness -> lifecycle status -> audit trail.

    Not a new workflow engine: every phase is an existing commit's own
    method, called unchanged --

        find applied strategies +      Commit #8 (backend.agent_strategy_feedback)
        record their outcomes          feedback_service.process_execution()
        recalculate effectiveness      Commit #4 scorer.score()
        evaluate lifecycle status      Commit #9 lifecycle_evaluator.evaluate()
        record the resulting decision  Commit #11 audit_service.record()

    This class holds no store of its own and introduces no new
    persistence: every one of those calls is already durable in its own
    existing way. process_execution() only ever reads the execution
    (LLMAgentPlanExecutionService.get()) -- never execute()/cancel() -- so
    a learning failure, however severe, can never alter the execution
    result it is learning from.

    Strategies are processed independently: one strategy's own score/
    lifecycle/audit step failing is caught, recorded as an "error"
    operation naming that strategy, and never stops the loop for any
    other strategy applied to the same execution -- outcome recording
    (Commit #8, itself all-or-nothing per strategy pair) is the only step
    whose failure stops the whole pipeline, since no strategy's evidence
    can be looked up at all without it.

    Idempotent per execution_id: before doing any work, process_execution()
    checks whether Commit #11's own audit trail already carries a LEARNED
    decision for this execution -- if so, this execution has already been
    through this pipeline, and the call is a no-op (SKIPPED) rather than
    re-running Commit #9's own evaluate() (which, called twice with
    unchanged evidence, would otherwise append a second, redundant
    lifecycle decision) or growing Commit #11's audit trail for no reason.
    Commit #8's own outcome recording is separately idempotent by
    (strategy_id, execution_id) regardless, so even a partially-processed
    execution (some strategies learned from, some not, from an earlier
    call that itself failed partway) never double-records an outcome
    when retried.
    """

    def __init__(
        self,
        plan_execution_service: LLMAgentPlanExecutionService,
        feedback_service: LLMAgentStrategyFeedbackService,
        scorer: LLMAgentStrategyScorer,
        lifecycle_evaluator: LLMAgentStrategyLifecycleEvaluator,
        audit_service: LLMAgentStrategyDecisionAuditService,
    ):
        self._plan_execution_service = plan_execution_service
        self._feedback_service = feedback_service
        self._scorer = scorer
        self._lifecycle_evaluator = lifecycle_evaluator
        self._audit_service = audit_service

    @staticmethod
    def _result(execution_id, status, operations, outcomes, scores, lifecycle_decisions, audit_decisions, now):
        return LLMAgentStrategyLearningResult(
            execution_id=execution_id, status=status, operations=operations, outcomes=outcomes,
            scores=scores, lifecycle_decisions=lifecycle_decisions, audit_decisions=audit_decisions,
            processed_at=now,
        )

    def _already_processed(self, execution_id: str) -> bool:
        return any(
            record.decision_type == LEARNED
            for record in self._audit_service.list_for_execution(execution_id)
        )

    def process_execution(self, execution_id: str, now: datetime = None) -> LLMAgentStrategyLearningResult:
        """Run the full learning pipeline for execution_id.

        Raises:
            UnknownAgentPlanExecutionError: If execution_id was never
                recorded (propagated, not wrapped)
        """
        now = now or datetime.now(timezone.utc)
        execution = self._plan_execution_service.get(execution_id)
        operations = [_operation("read_execution", "ok", f"status={execution.status}")]

        if execution.status == RUNNING:
            operations.append(_operation("eligibility", "skipped", "execution has not completed yet"))
            return self._result(execution_id, SKIPPED, operations, [], [], [], [], now)

        if self._already_processed(execution_id):
            operations.append(_operation("eligibility", "skipped", "execution already processed"))
            return self._result(execution_id, SKIPPED, operations, [], [], [], [], now)

        try:
            outcomes = self._feedback_service.process_execution(execution_id)
        except Exception as error:
            operations.append(_operation("record_outcomes", "error", str(error)))
            return self._result(execution_id, FAILED, operations, [], [], [], [], now)

        operations.append(
            _operation("record_outcomes", "ok", f"{len(outcomes)} strategy outcome(s) recorded")
        )

        if not outcomes:
            operations.append(
                _operation("learning", "skipped", "no strategies were applied for this execution")
            )
            return self._result(execution_id, PROCESSED, operations, [], [], [], [], now)

        scores, lifecycle_decisions, audit_decisions = [], [], []

        for outcome in outcomes:
            strategy_id = outcome.strategy_id

            try:
                score = self._scorer.score(strategy_id, now=now)
            except Exception as error:
                operations.append(_operation(f"score:{strategy_id}", "error", str(error)))
                continue
            scores.append(score)
            operations.append(
                _operation(f"score:{strategy_id}", "ok", f"score={score.score:.3f} confidence={score.confidence:.3f}")
            )

            try:
                lifecycle_decision = self._lifecycle_evaluator.evaluate(strategy_id, now=now)
            except Exception as error:
                operations.append(_operation(f"lifecycle:{strategy_id}", "error", str(error)))
                continue
            lifecycle_decisions.append(lifecycle_decision)
            operations.append(_operation(f"lifecycle:{strategy_id}", "ok", f"status={lifecycle_decision.status}"))

            try:
                audit_decision = self._audit_service.record(
                    strategy_id, execution_id, LEARNED, lifecycle_decision.status, lifecycle_decision.reason,
                    score=lifecycle_decision.score,
                    evidence={
                        "confidence": lifecycle_decision.confidence,
                        "evidence_count": lifecycle_decision.evidence_count,
                        "succeeded_count": lifecycle_decision.succeeded_count,
                        "failed_count": lifecycle_decision.failed_count,
                        "outcome_id": outcome.outcome_id,
                    },
                )
            except Exception as error:
                operations.append(_operation(f"audit:{strategy_id}", "error", str(error)))
                continue
            audit_decisions.append(audit_decision)
            operations.append(_operation(f"audit:{strategy_id}", "ok", f"decision_id={audit_decision.decision_id}"))

        return self._result(
            execution_id, PROCESSED, operations, outcomes, scores, lifecycle_decisions, audit_decisions, now
        )
