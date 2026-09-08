from datetime import datetime, timedelta, timezone

from backend.agent_capability_execution import RUNNING, LLMAgentCapabilityExecutionService

from .models import ACTION_CANCELLED, ACTION_NONE, ACTION_TIMED_OUT, ExecutionControlResult


class LLMAgentCapabilityExecutionControl:
    """Cancels a running Commit #7 capability execution, or closes one out
    once it has exceeded a configured deadline -- never a second
    lifecycle engine, scheduler, or timeout mechanism: every actual state
    change goes through Commit #7's own execution_service.fail(), the
    exact same existing state transition Commit #11's own
    LLMAgentCapabilityRecoveryService already reuses for its own RUNNING
    -> FAILED closure, and this class touches nothing else.

    Only RUNNING is a "repository-supported active state" (Rule:
    "cancellation is allowed only from repository-supported active
    states" / "never cancel or timeout terminal executions") -- Commit
    #7's own TERMINAL_STATUSES (SUCCEEDED, FAILED) are always refused by
    both cancel() and check_timeout(), reported as ACTION_NONE rather
    than raised, the same "an ordinary precondition miss is a structured
    result, not an exception" discipline every other *Result in this
    series already keeps. Because the resulting closure is always
    through Commit #7's own fail(), and that service already refuses to
    reopen a terminal record (TerminalCapabilityExecutionError), a
    caller who still tries to complete() an execution this class has
    already cancelled or timed out gets that existing guard for free --
    completion "after cancellation/timeout" is rejected by state
    semantics Commit #7 already enforces, never a second check invented
    here (Rule: "cancellation/timeout must prevent later completion from
    incorrectly marking the execution successful").

    Deadlines: Commit #7's own LLMAgentCapabilityExecution carries no
    deadline/timeout field of its own -- inspected and confirmed absent
    rather than assumed, and deliberately not retrofitted onto that
    already-established record now (Rule: "no unrelated refactors"; a
    new persisted field would touch every existing caller's
    understanding of that frozen dataclass for a concern that belongs at
    this layer, not the record's). Rather than inventing a persisted
    per-execution deadline, or a background poller to enforce one (both
    explicitly ruled out -- "no new scheduler, worker, queue, or runtime
    infrastructure"), this class accepts one optional, caller-configured
    `default_timeout_seconds` at construction time and computes a
    deadline on demand, per check, as `execution.started_at +
    default_timeout_seconds` -- the same "elapsed time since start
    versus a duration" arithmetic
    backend.llm.tool_control.LLMToolExecutionControlService already uses
    for its own (differently-shaped, persisted-at-start) timeout_at,
    applied here without persisting anything: nothing is scheduled,
    nothing runs in the background, and repeated check_timeout() calls
    for the same still-within-budget execution are pure, side-effect-free
    reads. When default_timeout_seconds is left unset, this control has
    no deadline representation to check against at all, and
    check_timeout() honestly reports exactly that (Rule: "if the
    repository has no actual timeout/deadline representation, implement
    only the cancellation path rather than inventing one") -- cancel()
    remains fully functional regardless.
    """

    def __init__(self, execution_service: LLMAgentCapabilityExecutionService, default_timeout_seconds: float = None):
        self._execution_service = execution_service
        self._default_timeout_seconds = default_timeout_seconds

    def cancel(self, execution_id: str, reason: str = None) -> ExecutionControlResult:
        """Cancel execution_id if it is currently RUNNING.

        Raises:
            UnknownCapabilityExecutionError: If execution_id was never
                started (propagated unchanged from
                LLMAgentCapabilityExecutionService.get())
        """
        execution = self._execution_service.get(execution_id)

        if execution.status != RUNNING:
            return ExecutionControlResult(
                execution_id=execution_id,
                action=ACTION_NONE,
                previous_status=execution.status,
                new_status=execution.status,
                reason=(
                    f"execution is {execution.status}, not RUNNING; cancellation only "
                    f"applies to an active execution"
                ),
            )

        message = f"cancelled: {reason}" if reason else "cancelled by request"
        closed = self._execution_service.fail(execution_id, message)
        return ExecutionControlResult(
            execution_id=execution_id,
            action=ACTION_CANCELLED,
            previous_status=RUNNING,
            new_status=closed.status,
            reason=message,
        )

    def check_timeout(self, execution_id: str, now: datetime = None) -> ExecutionControlResult:
        """Close execution_id out as timed out if it is RUNNING, a
        default_timeout_seconds was configured for this control, and now
        (default: the current time) is at or past
        execution.started_at + default_timeout_seconds.

        Raises:
            UnknownCapabilityExecutionError: If execution_id was never
                started (propagated unchanged, as cancel())
        """
        execution = self._execution_service.get(execution_id)
        now = now if now is not None else datetime.now(timezone.utc)

        if execution.status != RUNNING:
            return ExecutionControlResult(
                execution_id=execution_id,
                action=ACTION_NONE,
                previous_status=execution.status,
                new_status=execution.status,
                reason=(
                    f"execution is {execution.status}, not RUNNING; timeout only "
                    f"applies to an active execution"
                ),
            )

        if self._default_timeout_seconds is None:
            return ExecutionControlResult(
                execution_id=execution_id,
                action=ACTION_NONE,
                previous_status=execution.status,
                new_status=execution.status,
                reason="no deadline is configured for this control; timeout does not apply",
            )

        deadline = execution.started_at + timedelta(seconds=self._default_timeout_seconds)
        if now < deadline:
            return ExecutionControlResult(
                execution_id=execution_id,
                action=ACTION_NONE,
                previous_status=execution.status,
                new_status=execution.status,
                reason=f"execution has not yet reached its configured deadline ({deadline.isoformat()})",
            )

        message = (
            f"timed out: exceeded the configured {self._default_timeout_seconds}s deadline "
            f"({deadline.isoformat()})"
        )
        closed = self._execution_service.fail(execution_id, message)
        return ExecutionControlResult(
            execution_id=execution_id,
            action=ACTION_TIMED_OUT,
            previous_status=RUNNING,
            new_status=closed.status,
            reason=message,
        )
