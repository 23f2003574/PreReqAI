from backend.agent_capability_execution import FAILED, RUNNING, SUCCEEDED, LLMAgentCapabilityExecutionService

from .models import CapabilityRecoveryResult, RecoveryCheck


class LLMAgentCapabilityRecoveryService:
    """Recovers an interrupted or failed Commit #7 capability execution
    record, safely -- never a second recovery, retry, or scheduling
    framework, and never something that re-invokes a capability itself.

    Recoverability is judged entirely from Commit #7's own execution
    record and (optionally) the existing
    backend.llm.tool_retry.LLMToolRetryService's own retryable/
    non-retryable classification, the exact same "is this failure one
    the wired retry policy already treats as transient" question
    backend.agent_failure_handling.LLMAgentFailureService._is_retryable()
    already asks for an unrelated execution family (plan steps) --
    reused here via the same collaborator, never a second copy of that
    classification. LLMToolRetryService.should_retry() is called as a
    pure classifier only (constructed, or supplied, with no
    control_service/execution_service of its own): this module never
    touches its actual retry-with-backoff machinery, since retrying is
    explicitly out of scope here (Rule: "no new queue, scheduler, or
    worker system" / "never retry an execution blindly" -- recover()
    reports whether a fresh attempt is warranted, it never makes one).

    Two, and only two, repository-supported recoverable states exist:

        RUNNING  the record was never closed -- most plausibly because
                 the process that started it was interrupted before
                 calling complete()/fail(). Always recoverable: recover()
                 closes it as FAILED through Commit #7's own fail(),
                 never by reaching into the store directly, so the
                 closure is provenance-preserving and goes through the
                 exact same validation/terminal-state guard every other
                 caller of fail() already gets.
        FAILED   recoverable only when a retry_service is supplied *and*
                 classifies the record's own (already redacted) error as
                 retryable. Without a retry_service, FAILED is never
                 treated as recoverable -- the conservative default Rule
                 "never retry an execution blindly" demands: no wired
                 policy means no basis for treating a failure as safe to
                 retry. A FAILED record is already terminal, and Commit
                 #7's own service correctly refuses to reopen a terminal
                 record (TerminalCapabilityExecutionError); recovering a
                 retryable FAILED execution therefore never mutates the
                 original record at all -- it only reports the
                 recommendation ("start a fresh attempt via Commit #10's
                 lifecycle service"), leaving previous_status ==
                 new_status.

    SUCCEEDED is never recoverable, unconditionally (Rule: "terminal
    successful executions are never recovered"), matching
    backend.llm.tool_idempotency's own established rule that only a
    SUCCEEDED record is ever treated as final/immutable evidence of
    completion -- generalized here to "SUCCEEDED can never be revisited
    at all", the strongest form of that same idempotency guarantee.

    No checkpoint infrastructure (backend.agent_checkpointing) is
    reused: that module's own LLMAgentCheckpoint concept is a multi-step
    plan's own completed_steps trail, which has no analog for one atomic
    capability execution record -- there is nothing here to checkpoint,
    so "use existing checkpoint/state infrastructure where available"
    is satisfied vacuously (Rule's own "where available" qualifier).

    Both methods only ever read Commit #7's own execution_service (and,
    when given, the retry_service's own pure classifier) except for the
    one legitimate RUNNING -> FAILED transition, made exclusively through
    Commit #7's own fail(). recover() called on a non-recoverable
    execution leaves it completely untouched (Rule: "failed recovery
    leaves the original state consistent"), and no method here ever
    creates a second execution record for the same attempt (Rule:
    "recovery does not duplicate execution records incorrectly").
    """

    def __init__(self, execution_service: LLMAgentCapabilityExecutionService, retry_service=None):
        self._execution_service = execution_service
        self._retry_service = retry_service

    def can_recover(self, execution_id: str) -> RecoveryCheck:
        """Whether execution_id is currently eligible for recover().

        Raises:
            UnknownCapabilityExecutionError: If execution_id was never
                started (propagated unchanged from
                LLMAgentCapabilityExecutionService.get())
        """
        execution = self._execution_service.get(execution_id)

        if execution.status == SUCCEEDED:
            return RecoveryCheck(
                recoverable=False,
                execution_id=execution_id,
                status=execution.status,
                reason="execution already succeeded; terminal successful executions are never recovered",
            )

        if execution.status == RUNNING:
            return RecoveryCheck(
                recoverable=True,
                execution_id=execution_id,
                status=execution.status,
                reason="execution is still RUNNING and may have been interrupted; safe to close as failed",
            )

        # FAILED
        if self._retry_service is None:
            return RecoveryCheck(
                recoverable=False,
                execution_id=execution_id,
                status=execution.status,
                reason="no retry policy configured; refusing to retry blindly",
            )

        if self._retry_service.should_retry(execution.error):
            return RecoveryCheck(
                recoverable=True,
                execution_id=execution_id,
                status=execution.status,
                reason=f"failure is retryable per the configured retry policy: {execution.error}",
            )

        return RecoveryCheck(
            recoverable=False,
            execution_id=execution_id,
            status=execution.status,
            reason=f"failure is not retryable per the configured retry policy: {execution.error}",
        )

    def recover(self, execution_id: str) -> CapabilityRecoveryResult:
        """Recover execution_id if, and only if, can_recover() says so.

        Raises:
            UnknownCapabilityExecutionError: If execution_id was never
                started (propagated unchanged, as can_recover())
        """
        check = self.can_recover(execution_id)

        if not check.recoverable:
            return CapabilityRecoveryResult(
                recoverable=False,
                execution_id=execution_id,
                previous_status=check.status,
                new_status=check.status,
                reason=check.reason,
            )

        if check.status == RUNNING:
            closed = self._execution_service.fail(
                execution_id,
                "recovered: execution was interrupted while RUNNING and has been "
                "closed without a trusted outcome",
            )
            return CapabilityRecoveryResult(
                recoverable=True,
                execution_id=execution_id,
                previous_status=RUNNING,
                new_status=closed.status,
                reason=check.reason,
            )

        # FAILED and retryable: the record is already terminal and stays
        # exactly as it was -- see the class docstring for why.
        return CapabilityRecoveryResult(
            recoverable=True,
            execution_id=execution_id,
            previous_status=check.status,
            new_status=check.status,
            reason=check.reason,
        )
