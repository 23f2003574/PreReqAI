from datetime import datetime

from backend.agent_memory_learning_orchestration import LLMAgentMemoryLearningOrchestrator
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.llm.tool_execution import FAILED, SUCCEEDED


class LLMAgentMemoryLearningIntegration:
    """Wires Commit #12's learning orchestrator into the real agent
    execution lifecycle, so a completed execution automatically attempts
    to turn itself into learning.

    Not a second execution path or a new event bus: execute() calls
    Commit #4's own LLMAgentPlanExecutionService.execute() -- the one,
    unchanged, existing execution loop, including whichever
    on_created/before_step/after_step hooks a caller already supplies --
    and only once that call returns a completed LLMAgentPlanExecution
    does this service do anything further. This is the exact "call the
    real method, then act on its result" pattern
    backend.agent_orchestration.LLMAgentOrchestrationService.resume()
    already establishes for replaying context/checkpoints after Commit
    #6's recover() -- there is no dedicated "on completed" hook anywhere
    in the repository to attach to instead, and inventing one here would
    be exactly the new event bus/lifecycle framework the rules forbid.

    on_execution_completed() is the actual integration point, and is
    directly callable on its own for an execution that was run some other
    way (not necessarily through this service's own execute()). It:

        1. re-reads execution_id through Commit #4's own get() -- the
           existing persisted outcome, never a second copy of it
        2. only proceeds once that status is genuinely terminal
           (RUNNING is left alone) and evidence-bearing (SUCCEEDED or
           FAILED -- both preserved as eligible, since Commit #1/#8/#9's
           own eligibility already treats a captured failure as real
           evidence, not noise; REJECTED/CANCELLED carry no strategy
           verdict and are left alone too)
        3. invokes Commit #12's own orchestrator -- process_memory() when
           a memory_id is given (typically because this execution's
           outcome is evidence *about* an existing memory, the same
           execution_id-need-not-equal-the-memory's-own-origin relationship
           Commit #5's feedback already allows), or process_execution()
           otherwise, exactly Commit #12's own two entry points, neither
           reimplemented nor extended here
        4. records the resulting LLMAgentMemoryLearningResult, retrievable
           via learning_result_for() -- Commit #12's own provenance,
           preserved rather than discarded

    Idempotent by construction: each execution_id is only ever passed to
    the orchestrator once, tracked in a small in-process set -- the same
    "service holds its own small internal state" pattern
    backend.agent_execution_budget already uses for its own usage/limits,
    not a new persistence subsystem. A repeat call for an execution_id
    already processed is a safe no-op that does not touch the
    orchestrator again; learning_result_for() still returns whatever the
    first call produced.

    A learning failure can never reach, or change, the execution's own
    result: on_execution_completed() catches any exception the
    orchestrator itself does not already catch and contain (Commit #12's
    own process_execution()/process_memory() already report a step
    failure as a FAILED LLMAgentMemoryLearningResult rather than raising,
    so this is a last-resort safety net, not the primary handling) and
    never re-raises. execute() always returns exactly the
    LLMAgentPlanExecution Commit #4 produced, whatever happened during
    learning -- callers who never look at learning_result_for() see
    exactly the same behavior this service had before it existed.
    """

    def __init__(
        self,
        plan_execution_service: LLMAgentPlanExecutionService,
        learning_orchestrator: LLMAgentMemoryLearningOrchestrator,
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
        memory_id: str = None,
        now: datetime = None,
    ):
        """Run plan_id exactly as Commit #4's own execute() already does,
        then attempt to learn from it once it completes.

        Every hook a caller passes through is Commit #4's own, unmodified
        -- this adds no hook of its own to that loop, and never wraps or
        replaces any of them. The return value is always exactly what
        Commit #4's execute() itself produced.
        """
        execution = self._plan_execution_service.execute(
            plan_id, subject, timeout=timeout,
            on_created=on_created, before_step=before_step, after_step=after_step,
        )
        self.on_execution_completed(execution.execution_id, memory_id=memory_id, now=now)
        return execution

    def on_execution_completed(self, execution_id: str, memory_id: str = None, now: datetime = None):
        """Attempt to learn from execution_id, once, if it is eligible.

        Returns Commit #12's own LLMAgentMemoryLearningResult, or None
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
            if memory_id is not None:
                result = self._learning_orchestrator.process_memory(memory_id, now=now)
            else:
                result = self._learning_orchestrator.process_execution(execution_id, now=now)
        except Exception:
            return None

        self._results_by_execution[execution_id] = result
        return result

    def learning_result_for(self, execution_id: str):
        """The LLMAgentMemoryLearningResult on_execution_completed()
        produced for execution_id, or None if it was never (successfully)
        processed."""
        return self._results_by_execution.get(execution_id)
