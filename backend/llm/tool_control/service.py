import dataclasses
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timedelta, timezone
from numbers import Real
from threading import RLock

from ..tool_execution import (
    CANCELLED,
    RUNNING,
    TERMINAL_STATUSES,
    TIMED_OUT,
    LLMToolExecution,
    LLMToolExecutionService,
)
from ..tool_invocation import LLMToolInvocationPlan


class InvalidTimeoutError(ValueError):
    """Raised when execute_with_timeout() is given a non-positive timeout."""


class UnknownControlledExecutionError(KeyError):
    """Raised when cancel()/status()/get() names an execution this service
    never started."""


class ExecutionAlreadyCompletedError(ValueError):
    """Raised when cancel() is called on an execution that already finished.

    Matches ExecutionRuntimeCancellationService, which refuses to cancel a
    runtime that is not active while still treating a repeat cancellation of
    an already-cancelled one as a no-op.
    """


class LLMToolExecutionControlService:
    """Bounds how long a tool call may run, and lets one be cancelled.

    Follows the repository's existing timeout and cancellation model rather
    than adding a task framework:

        ExecutionRuntimeTimeoutService       -- a deadline is armed from now,
                                                checked against the clock, and
                                                on expiry the work is driven to
                                                a terminal state. It never kills
                                                anything either
        ExecutionRuntimeCancellationService  -- cancellation is idempotent
                                                (re-cancelling returns the
                                                record unchanged), refuses
                                                anything not active, and guards
                                                all state with an RLock

    Everything that decides whether a call may run at all is Commit #5's,
    unchanged: execute_with_timeout() puts that service's execute() behind a
    deadline, so the registry check, Commit #4 authorization and the Commit
    #2 argument revalidation all still happen, in that order, before a tool
    is touched. When an idempotency service is supplied, Commit #9's
    execute_once() is used instead, so a duplicate call still runs once.

    How a deadline interacts with idempotency is worth stating exactly,
    because it is not "a timeout is never memoized". The caller's verdict
    and the work's fate are separate facts. If the orphaned work never
    succeeds, Commit #9 memoizes nothing and a retry genuinely re-executes.
    If it does succeed after the deadline, Commit #9 memoizes that success,
    so a retry returns it rather than running the tool a second time --
    which is the whole point of an idempotency key, and avoids duplicating
    whatever side effect the first run already had. Either way the timed-out
    call's own record stays TIMED_OUT.

    An honest limitation, stated plainly: Python cannot safely kill a
    running thread, and this repository has no preemption primitive (no
    signals, no process pools) to borrow. A deadline therefore releases the
    caller and marks the execution TIMED_OUT; a handler that is genuinely
    stuck keeps running in its worker until it returns on its own. What is
    guaranteed is what the rules require -- the caller never hangs, the
    verdict is recorded truthfully, and a late result is discarded rather
    than promoted: an execution that timed out or was cancelled is never
    later reported as successful. Late arrivals are recorded as superseded
    and listed by orphaned().
    """

    def __init__(
        self,
        execution_service: LLMToolExecutionService,
        idempotency_service=None,
        audit_service=None,
        max_workers: int = 8,
    ):
        self._execution_service = execution_service
        self._idempotency_service = idempotency_service
        self._audit_service = audit_service
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._records = {}
        self._orphaned = []
        self._counter = 0
        self._lock = RLock()

    @property
    def execution_service(self) -> LLMToolExecutionService:
        """The Commit #5 engine this service puts a deadline in front of."""
        return self._execution_service

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _validate_timeout(timeout):
        if (
            timeout is None
            or isinstance(timeout, bool)
            or not isinstance(timeout, Real)
            or timeout <= 0
        ):
            raise InvalidTimeoutError(
                f"Cannot execute with a non-positive timeout: {timeout!r}."
            )

    def _store(self, record: LLMToolExecution, *aliases) -> LLMToolExecution:
        with self._lock:
            self._records[record.execution_id] = record
            for alias in aliases:
                if alias:
                    self._records[alias] = record
            return record

    def _resolve(self, execution_id: str) -> LLMToolExecution:
        with self._lock:
            try:
                return self._records[execution_id]
            except KeyError:
                raise UnknownControlledExecutionError(execution_id)

    def _run(self, plan, subject) -> LLMToolExecution:
        """One genuine execution, through the gates of whichever service owns them."""
        if self._idempotency_service is not None:
            return self._idempotency_service.execute_once(plan, subject)
        return self._execution_service.execute(plan, subject)

    # -- the deadline ------------------------------------------------------

    def execute_with_timeout(self, plan, subject, timeout) -> LLMToolExecution:
        """Run a plan, giving up on waiting after `timeout` seconds.

        Returns the completed execution record, or a TIMED_OUT record if the
        deadline passed first. Never raises for a slow or failing tool.
        """
        if not isinstance(plan, LLMToolInvocationPlan):
            raise TypeError(
                f"Cannot execute something that is not an LLMToolInvocationPlan: {plan!r}."
            )
        self._validate_timeout(timeout)

        started_at = datetime.now(timezone.utc)

        with self._lock:
            self._counter += 1
            control_id = f"tool-control-{self._counter}"

        pending = LLMToolExecution(
            execution_id=control_id,
            plan_id=plan.plan_id,
            tool_name=plan.tool_name,
            status=RUNNING,
            result=None,
            error=None,
            started_at=started_at,
            completed_at=None,
            timeout_at=started_at + timedelta(seconds=timeout),
        )
        self._store(pending)

        future = self._pool.submit(self._run, plan, subject)

        try:
            completed = future.result(timeout=timeout)
        except FutureTimeoutError:
            record = self._mark_timed_out(control_id)
            # The worker is still running and cannot be killed. When it does
            # finish, whatever it produced is recorded as superseded rather
            # than allowed to overwrite this verdict.
            future.add_done_callback(lambda f: self._supersede(control_id, f))
            self._audit(record)
            return record

        return self._settle(control_id, completed)

    def _mark_timed_out(self, control_id: str) -> LLMToolExecution:
        with self._lock:
            current = self._records[control_id]
            if current.status != RUNNING:
                return current
            record = dataclasses.replace(
                current,
                status=TIMED_OUT,
                result=None,
                error=(
                    f"tool {current.tool_name!r} did not return before its deadline "
                    f"({current.timeout_at.isoformat()})"
                ),
                completed_at=datetime.now(timezone.utc),
            )
            return self._store(record)

    def _settle(self, control_id: str, completed: LLMToolExecution) -> LLMToolExecution:
        """Fold a finished execution into its control record.

        A control record that was cancelled while the work was in flight
        keeps its CANCELLED verdict; the result is discarded rather than
        promoted to a success.
        """
        with self._lock:
            current = self._records[control_id]

            if current.status != RUNNING:
                self._orphaned.append(completed)
                return current

            record = dataclasses.replace(
                completed,
                timeout_at=current.timeout_at,
                cancelled_at=current.cancelled_at,
            )
            # Reachable by the control id and by the execution service's own id.
            self._store(record, control_id)
            self._audit(record)
            return record

    def _supersede(self, control_id: str, future):
        """Record a result that arrived after its deadline or cancellation."""
        try:
            late = future.result()
        except Exception:
            return
        with self._lock:
            self._orphaned.append(late)

    def _audit(self, record: LLMToolExecution):
        if self._audit_service is not None:
            self._audit_service.record_execution(record)

    # -- cancellation ------------------------------------------------------

    def cancel(self, execution_id: str, reason: str = "cancelled by request"):
        """Cancel an in-flight execution.

        Idempotent: cancelling an already-cancelled execution returns it
        unchanged, exactly as ExecutionRuntimeCancellationService does.
        An execution that already finished cannot be cancelled.
        """
        with self._lock:
            record = self._resolve(execution_id)

            if record.status == CANCELLED:
                return record

            if record.status in TERMINAL_STATUSES:
                raise ExecutionAlreadyCompletedError(
                    f"Cannot cancel execution {execution_id!r}: it is already "
                    f"{record.status}."
                )

            now = datetime.now(timezone.utc)
            cancelled = dataclasses.replace(
                record,
                status=CANCELLED,
                result=None,
                error=reason,
                cancelled_at=now,
                completed_at=now,
            )
            self._store(cancelled, execution_id)
            self._audit(cancelled)
            return cancelled

    # -- reads -------------------------------------------------------------

    def status(self, execution_id: str) -> str:
        return self._resolve(execution_id).status

    def get(self, execution_id: str) -> LLMToolExecution:
        return self._resolve(execution_id)

    def orphaned(self) -> list:
        """Results that arrived after their call had already timed out or been
        cancelled, and were therefore discarded."""
        with self._lock:
            return list(self._orphaned)

    def shutdown(self, wait: bool = True):
        self._pool.shutdown(wait=wait)
