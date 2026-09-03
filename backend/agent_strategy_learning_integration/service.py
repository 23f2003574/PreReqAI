from datetime import datetime

from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_strategy_learning_orchestration import LLMAgentStrategyLearningOrchestrator
from backend.llm.tool_execution import FAILED, SUCCEEDED


class LLMAgentStrategyLearningIntegration:
    """Wires Commit #12's strategy-learning orchestrator into the real
    agent execution lifecycle, so a completed execution automatically
    attempts to turn itself into strategy learning.

    Not a second execution path or a new event bus: execute() calls
    backend.agent_plan_execution.LLMAgentPlanExecutionService.execute()
    -- the one, unchanged, existing execution loop, including whichever
    on_created/before_step/after_step hooks a caller already supplies --
    and only once that call returns a completed LLMAgentPlanExecution
    does this service do anything further. This is the exact "call the
    real method, then act on its result" pattern
    backend.agent_memory_learning_integration.LLMAgentMemoryLearningIntegration
    already establishes for the memory series -- there is no dedicated
    "on completed" hook anywhere in the repository to attach to instead,
    and inventing one here would be exactly the new event bus/lifecycle
    framework the rules forbid.

    on_execution_completed() is the actual integration point, and is
    directly callable on its own for an execution that was run some other
    way (not necessarily through this service's own execute()). It:

        1. re-reads execution_id through
           LLMAgentPlanExecutionService.get() -- the existing persisted
           outcome, never a second copy of it
        2. only proceeds once that status is genuinely terminal (RUNNING
           is left alone) and evidence-bearing (SUCCEEDED or FAILED --
           both eligible, since Commit #3/#8's own eligibility already
           treats a captured failure as real strategy evidence, not
           noise; REJECTED/CANCELLED carry no strategy verdict and are
           left alone too)
        3. invokes Commit #12's own orchestrator -- process_execution(),
           its one entry point, neither reimplemented nor extended here
        4. records the resulting LLMAgentStrategyLearningResult,
           retrievable via learning_result_for() -- Commit #12's own
           provenance, preserved rather than discarded

    Idempotent by construction, at two independent levels: each
    execution_id is only ever passed to the orchestrator once from this
    service, tracked in a small in-process set -- the same "service holds
    its own small internal state" pattern
    backend.agent_execution_budget already uses for its own usage/limits,
    not a new persistence subsystem -- and Commit #12's own
    process_execution() is separately idempotent regardless (it checks
    Commit #11's own audit trail before doing any work). A repeat call
    for an execution_id already processed here is a safe no-op that does
    not touch the orchestrator again; learning_result_for() still returns
    whatever the first call produced.

    A learning failure can never reach, or change, the execution's own
    result: on_execution_completed() catches any exception the
    orchestrator itself does not already catch and contain (Commit #12's
    own process_execution() already reports a per-strategy failure as an
    "error" operation inside a PROCESSED
    LLMAgentStrategyLearningResult rather than raising, so this is a
    last-resort safety net, not the primary handling) and never re-raises.
    execute() always returns exactly the LLMAgentPlanExecution the real
    execution service produced, whatever happened during learning --
    callers who never look at learning_result_for() see exactly the same
    behavior this service had before it existed, including when no
    strategy was ever applied to the execution at all (Commit #12's own
    process_execution() reports that case as PROCESSED with empty result
    lists, never an error).
    """

    def __init__(
        self,
        plan_execution_service: LLMAgentPlanExecutionService,
        learning_orchestrator: LLMAgentStrategyLearningOrchestrator,
    ):
        self._plan_execution_service = plan_execution_service
        self._learning_orchestrator = learning_orchestrator
        self._processed_execution_ids = set()
        self._results_by_execution = {}

    def execute(
        self,
        plan_id: str,
        subject,
        timeout: float = None,
        on_created=None,
        before_step=None,
        after_step=None,
        now: datetime = None,
    ):
        """Run plan_id exactly as the real execute() already does, then
        attempt to learn from it once it completes.

        Every hook a caller passes through is the real, unmodified
        execution service's own -- this adds no hook of its own to that
        loop, and never wraps or replaces any of them. The return value
        is always exactly what the real execute() itself produced.
        """
        execution = self._plan_execution_service.execute(
            plan_id, subject, timeout=timeout,
            on_created=on_created, before_step=before_step, after_step=after_step,
        )
        self.on_execution_completed(execution.execution_id, now=now)
        return execution

    def on_execution_completed(self, execution_id: str, now: datetime = None):
        """Attempt to learn from execution_id, once, if it is eligible.

        Returns Commit #12's own LLMAgentStrategyLearningResult, or None
        when nothing was (newly) attempted: execution_id is not yet
        terminal, its terminal status carries no learnable evidence
        (REJECTED/CANCELLED), it was already processed before, or the
        attempt itself raised something Commit #12 did not already catch.
        Never raises.
        """
        if execution_id in self._processed_execution_ids:
            return None

        execution = self._plan_execution_service.get(execution_id)
        if execution.status not in (SUCCEEDED, FAILED):
            return None

        self._processed_execution_ids.add(execution_id)

        try:
            result = self._learning_orchestrator.process_execution(execution_id, now=now)
        except Exception:
            return None

        self._results_by_execution[execution_id] = result
        return result

    def learning_result_for(self, execution_id: str):
        """The LLMAgentStrategyLearningResult on_execution_completed()
        produced for execution_id, or None if it was never (successfully)
        processed."""
        return self._results_by_execution.get(execution_id)
