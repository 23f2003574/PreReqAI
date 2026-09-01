from threading import RLock

from backend.llm.context import LLMContextService
from backend.llm.tool_execution import SUCCEEDED
from backend.llm.tool_results import LLMToolResult, LLMToolResultService


class UnverifiedStepResultError(ValueError):
    """Raised when record_step() is given a result that does not match
    Commit #3's own record for it -- a result must be verified before it
    can enter context, the same discipline Commit #6 applies to a
    checkpoint's claimed-complete steps."""


class UnknownAgentExecutionContextError(KeyError):
    """Raised when context() is given an execution_id with no recorded steps."""


class UnknownStepContextError(KeyError):
    """Raised when for_step() is given a step_id never recorded for that execution."""


class DuplicateStepContextError(ValueError):
    """Raised when record_step() is given a step_id already recorded with a
    *different* result. Re-recording the exact same (already-verified)
    result -- as happens after Commit #6 recovery replays a step that
    completed before an interruption -- is a safe no-op instead."""


def _tool_name_for(plan, step_id: str):
    return next((step.tool_name for step in plan.steps if step.step_id == step_id), None)


class LLMAgentExecutionContextService:
    """Feeds a plan execution's own completed step results back into LLM context.

    Not a second context system: every item this service adds is built by
    the existing backend.llm.tool_results.LLMToolResultService.context() --
    the same normalization, redaction, and token-budget validation every
    other tool result already goes through -- and stored via the existing
    backend.llm.context.LLMContextService, one context per execution_id.
    This service adds only what neither of those already knows: which
    agent step a result belongs to, and verifying it against Commit #3's
    own record before it is trusted at all.

    A step's result is included only once it is genuinely terminal --
    every backend.agent_step_execution.LLMAgentStepExecution a caller could
    ever hand to record_step() already is one, since Commit #3's
    execute_step() never returns anything else. SUCCEEDED steps carry
    their own Commit #6 (Commit #5/#6's own reused) LLMToolResult straight
    through; every other status (FAILED, DENIED, REJECTED, TIMED_OUT,
    CANCELLED) is represented by a synthetic LLMToolResult built from that
    same record's own status and error, so a failed step is never silently
    dropped or mistaken for a success -- it still goes through the exact
    same validate()/redact() gate a real result does.
    """

    def __init__(
        self,
        planning_service,
        step_execution_service,
        context_service: LLMContextService = None,
        result_service: LLMToolResultService = None,
    ):
        self._planning_service = planning_service
        self._step_execution_service = step_execution_service
        self._context_service = context_service or LLMContextService()
        self._result_service = result_service or LLMToolResultService()
        self._entries_by_execution = {}
        self._initialized = set()
        self._lock = RLock()

    @staticmethod
    def _context_id(execution_id: str) -> str:
        return f"agent-context-{execution_id}"

    def _ensure_context(self, execution_id: str, token_budget: int = None) -> str:
        context_id = self._context_id(execution_id)
        with self._lock:
            if execution_id not in self._initialized:
                self._context_service.create(context_id, token_budget=token_budget)
                self._initialized.add(execution_id)
                self._entries_by_execution[execution_id] = []
            return context_id

    def _to_tool_result(self, step_execution) -> LLMToolResult:
        if step_execution.status == SUCCEEDED:
            return step_execution.result

        plan = self._planning_service.get(step_execution.plan_id)
        return LLMToolResult(
            execution_id=step_execution.execution_id,
            status=step_execution.status,
            output=None,
            error=step_execution.error or step_execution.status,
            metadata={
                "tool_name": _tool_name_for(plan, step_execution.step_id),
                "plan_id": step_execution.plan_id,
                "truncated": False,
            },
        )

    def record_step(self, execution_id: str, step_id: str, result, priority: int = 0, token_budget: int = None):
        """Verify one step's outcome and add it to execution_id's running context.

        `result` is the Commit #3 LLMAgentStepExecution for `step_id` --
        checked against that service's own store before it is trusted.
        Re-recording the exact same, already-recorded result for a step is
        a safe no-op (this is what replaying Commit #6 recovery's steps
        looks like); recording a *different* result for an already-recorded
        step_id is refused.

        Raises:
            ValueError: If result.step_id does not match step_id
            UnverifiedStepResultError: If result does not match Commit #3's
                own record for its execution_id
            DuplicateStepContextError: If step_id was already recorded with
                a different result
        """
        if result.step_id != step_id:
            raise ValueError(f"result is for step {result.step_id!r}, not {step_id!r}")

        verified = self._step_execution_service.get(result.execution_id)
        if verified != result:
            raise UnverifiedStepResultError(
                f"result for step {step_id!r} does not match Commit #3's own record "
                f"for execution {result.execution_id!r}"
            )

        context_id = self._ensure_context(execution_id, token_budget=token_budget)

        with self._lock:
            entries = self._entries_by_execution[execution_id]
            existing = next((entry for entry in entries if entry["step_id"] == step_id), None)
            if existing is not None:
                if existing["execution_id"] == result.execution_id:
                    return existing["item"]
                raise DuplicateStepContextError(
                    f"step {step_id!r} was already recorded for execution {execution_id!r} "
                    f"with a different result"
                )

        tool_result = self._to_tool_result(verified)
        item = self._result_service.context(tool_result, priority=priority)
        item = self._context_service.add(context_id, item)

        with self._lock:
            self._entries_by_execution[execution_id].append(
                {"step_id": step_id, "execution_id": result.execution_id, "status": result.status, "item": item}
            )
        return item

    def context(self, execution_id: str) -> dict:
        """The assembled, token-budget-trimmed context for execution_id.

        Delegates entirely to Commit context infra's own
        LLMContextService.build() -- the same budget enforcement and
        insertion-order preservation every other LLM request already gets.

        Raises:
            UnknownAgentExecutionContextError: If no step has ever been
                recorded for execution_id
        """
        if execution_id not in self._initialized:
            raise UnknownAgentExecutionContextError(execution_id)
        return self._context_service.build(self._context_id(execution_id))

    def for_step(self, execution_id: str, step_id: str):
        """The LLMContextItem recorded for one step of execution_id.

        Raises:
            UnknownAgentExecutionContextError: If execution_id has no
                recorded steps at all
            UnknownStepContextError: If step_id itself was never recorded
        """
        if execution_id not in self._initialized:
            raise UnknownAgentExecutionContextError(execution_id)

        with self._lock:
            entry = next(
                (e for e in self._entries_by_execution[execution_id] if e["step_id"] == step_id), None
            )
        if entry is None:
            raise UnknownStepContextError(step_id)
        return entry["item"]

    def steps(self, execution_id: str) -> list:
        """step_ids recorded for execution_id, in the order record_step() was called."""
        if execution_id not in self._initialized:
            raise UnknownAgentExecutionContextError(execution_id)
        with self._lock:
            return [entry["step_id"] for entry in self._entries_by_execution[execution_id]]
