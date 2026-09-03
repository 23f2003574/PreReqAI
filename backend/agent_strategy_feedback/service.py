from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_strategy_effectiveness import LLMAgentStrategyOutcome, LLMAgentStrategyOutcomeService
from backend.agent_strategy_usage import LLMAgentStrategyUsageService


class LLMAgentStrategyFeedbackService:
    """Feeds one completed execution's real result back into every Commit
    #1 strategy that was actually applied for it, closing the loop Commit
    #7's usage tracking opened.

    Not a second outcome or analytics subsystem: process_execution() only
    ever orchestrates two existing services -- Commit #7's own
    LLMAgentStrategyUsageService.list_for_execution() to find which
    strategies were actually applied, and Commit #3's own
    LLMAgentStrategyOutcomeService.record() to create/link each one's
    outcome. Nothing here re-derives an execution's result, screens
    evidence, or scores effectiveness a second way: record() already does
    the verified-result derivation (it re-reads
    LLMAgentPlanExecutionService.get(execution_id) itself and only ever
    accepts a genuinely terminal, meaningful status), and Commit #4's own
    LLMAgentStrategyScorer is left completely untouched here -- scoring
    keeps reading Commit #3's outcome history exactly as it always has,
    so it sees this feedback's new evidence automatically the next time
    it is asked to score, without this service calling it at all.

    Only strategies Commit #7 marked applied=True are ever counted:
    a strategy merely selected as a candidate, never actually applied,
    contributes no effectiveness evidence. Both this service and Commit
    #3's own record() are read-only with respect to execution state --
    only LLMAgentPlanExecutionService.get() is ever called, never
    cancel()/execute() -- so processing feedback (successfully or not)
    can never alter the completed execution it is learning from.

    process_execution() is idempotent for the same execution_id: it
    delegates entirely to Commit #3's own idempotent-by-(strategy_id,
    execution_id) record(), so calling it again after some (or all) of an
    execution's applied strategies were already processed returns the
    same outcome records rather than duplicating any of them. Mixed or
    contradictory outcomes across an execution's different applied
    strategies (one strategy's usage leading to a SUCCEEDED-derived
    outcome, another's to a FAILED one) are never reconciled or dropped --
    each strategy gets its own outcome record, independently.
    """

    def __init__(
        self,
        plan_execution_service: LLMAgentPlanExecutionService,
        usage_service: LLMAgentStrategyUsageService,
        outcome_service: LLMAgentStrategyOutcomeService,
    ):
        self._plan_execution_service = plan_execution_service
        self._usage_service = usage_service
        self._outcome_service = outcome_service

    def update_strategy(self, strategy_id: str, outcome) -> LLMAgentStrategyOutcome:
        """Create/link strategy_id's Commit #3 outcome record for the
        execution `outcome` resolves to.

        `outcome` is the real, already-resolved
        backend.agent_plan_execution.LLMAgentPlanExecution record (e.g.
        from LLMAgentPlanExecutionService.get()) -- its own execution_id
        is what gets linked, and its status is never trusted directly:
        Commit #3's own record() re-reads and re-verifies the execution
        itself before deriving result, the exact same discipline it
        already applies to every other caller.

        Raises:
            UnknownAgentStrategyError: If strategy_id was never created by
                Commit #1 (propagated, not wrapped)
            UnknownAgentPlanExecutionError, IncompleteExecutionError,
            NonMeaningfulOutcomeError: Propagated from Commit #3's own
                record(), unchanged
        """
        return self._outcome_service.record(strategy_id, outcome.execution_id)

    def process_execution(self, execution_id: str) -> list:
        """Feed execution_id's result back into every strategy Commit #7
        marked applied=True for it.

        Strategies whose usage was only ever selected (applied=False) are
        skipped entirely -- they contribute no effectiveness evidence for
        this execution. Every applied strategy is processed independently:
        one strategy's outcome (or a failure recording it) never affects
        whether another strategy in the same execution is processed.

        Raises:
            UnknownAgentPlanExecutionError: If execution_id was never
                recorded (propagated, not wrapped, from Commit #7's own
                list_for_execution())
        """
        usages = self._usage_service.list_for_execution(execution_id)
        applied_usages = [usage for usage in usages if usage.applied]
        if not applied_usages:
            return []

        outcome = self._plan_execution_service.get(execution_id)

        return [self.update_strategy(usage.strategy_id, outcome) for usage in applied_usages]
