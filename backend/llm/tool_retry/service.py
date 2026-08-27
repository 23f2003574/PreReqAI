import time
from threading import RLock

from ..retry import LLMRetryService
from ..tool_execution import SUCCEEDED, LLMToolExecution
from ..tool_invocation import LLMToolInvocationPlan
from .models import NEVER_RETRYABLE_STATUSES, DEFAULT_POLICY, LLMToolRetryPolicy


class LLMToolRetryService:
    """Retries a failing tool call, explicitly and within bounds (Commit #11).

    Not a second retry framework. The schedule, the policy shape and the
    retryable/non-retryable distinction are all the existing
    backend.llm.retry module's:

        LLMRetryPolicy            -- LLMToolRetryPolicy converts to one, and
                                     validates through its validate()
        LLMRetryService.compute_backoff
                                  -- the one exponential schedule, called here
                                     rather than reimplemented
        TransientLLMError         -- the default, and only, retryable failure,
                                     matching that service's rule that
                                     everything else fails immediately

    What differs is the layer, and one deliberate consequence of it.
    LLMRetryService raises RetryExhaustedError when attempts run out, because
    a provider call either returns a response or does not. At this layer
    every outcome is already a record -- Commit #5 records a failure rather
    than raising it -- so exhaustion returns the final LLMToolExecution
    instead. That keeps the tool stack consistent: Commit #6 can normalize
    the result, Commit #8 can audit it, and attempts() says how many tries it
    took.

    Bounds and refusals:
    - A gate's refusal is never retried. DENIED (Commit #4 authorization) and
      REJECTED (Commit #2 validation) mean the call never reached the tool;
      retrying would re-run the same decision and treat a permission or
      schema verdict as a transient blip. A policy cannot opt into it.
    - CANCELLED stops retrying at once. A caller that cancelled did not ask
      for another attempt.
    - Timeouts are respected by running each attempt through Commit #10's
      execute_with_timeout when a timeout is given, so an attempt cannot hang
      and consume the whole budget.
    - Every attempt of one logical call shares a single attempt count,
      reachable by any attempt's execution_id.
    """

    def __init__(
        self,
        control_service=None,
        execution_service=None,
        policy: LLMToolRetryPolicy = None,
        audit_service=None,
        sleeper=time.sleep,
    ):
        """
        Args:
            control_service: Commit #10's control service. Required to honour
                a timeout; each attempt runs through its execute_with_timeout
            execution_service: Commit #5's engine, used when no timeout is in
                play. Defaults to the control service's own
            policy: The retry policy. Defaults to DEFAULT_POLICY
            audit_service: Commit #8's trail. Every attempt is appended, so
                the trail shows the retries rather than hiding them
            sleeper: Injectable sleep, so a test can assert the schedule
                without waiting on it
        """
        if control_service is None and execution_service is None:
            raise ValueError(
                "a control_service (Commit #10) or execution_service (Commit #5) "
                "is required"
            )
        self._control_service = control_service
        self._execution_service = execution_service
        self._policy = policy or DEFAULT_POLICY
        self._audit_service = audit_service
        self._sleep = sleeper
        self._attempts = {}
        self._delays = {}
        self._lock = RLock()

    @property
    def policy(self) -> LLMToolRetryPolicy:
        return self._policy

    # -- the retryable decision -------------------------------------------

    def should_retry(self, error) -> bool:
        """Whether `error` is one this policy explicitly allows retrying.

        Accepts an exception instance, an LLMToolExecution record, or the
        error string a record carries. Commit #5 stores a failure as
        "ClassName: detail" rather than the exception itself, so a record is
        matched on that leading class name -- which is why retryable_errors
        may also be given status strings, matched directly.
        """
        if not self._policy.enabled:
            return False

        if isinstance(error, LLMToolExecution):
            if error.status in NEVER_RETRYABLE_STATUSES:
                return False
            if error.status == SUCCEEDED:
                return False
            if self._matches_status(error.status):
                return True
            return self._matches_error_text(error.error)

        if isinstance(error, BaseException):
            classes = tuple(
                entry for entry in self._policy.retryable_errors if isinstance(entry, type)
            )
            return bool(classes) and isinstance(error, classes)

        if isinstance(error, str):
            return self._matches_status(error) or self._matches_error_text(error)

        return False

    def _matches_status(self, status) -> bool:
        return any(
            entry == status
            for entry in self._policy.retryable_errors
            if isinstance(entry, str)
        )

    def _matches_error_text(self, text) -> bool:
        if not text:
            return False
        leading = text.split(":", 1)[0].strip()
        return any(
            entry.__name__ == leading
            for entry in self._policy.retryable_errors
            if isinstance(entry, type)
        )

    # -- attempts ----------------------------------------------------------

    def attempts(self, execution_id: str) -> int:
        """How many attempts the logical call this execution belongs to took."""
        with self._lock:
            return self._attempts.get(execution_id, 0)

    def delays(self, execution_id: str) -> list:
        """The backoff delays actually waited between this call's attempts."""
        with self._lock:
            return list(self._delays.get(execution_id, []))

    def _record_attempt(self, ids: list, count: int, delays: list):
        with self._lock:
            for execution_id in ids:
                self._attempts[execution_id] = count
                self._delays[execution_id] = list(delays)

    # -- execution ---------------------------------------------------------

    def _run_once(self, plan, subject, timeout) -> LLMToolExecution:
        if timeout is not None:
            if self._control_service is None:
                raise ValueError("a control_service is required to honour a timeout")
            return self._control_service.execute_with_timeout(plan, subject, timeout)

        service = self._execution_service or self._control_service.execution_service
        return service.execute(plan, subject)

    def execute(self, plan, subject, timeout=None) -> LLMToolExecution:
        """Run a plan, retrying only what the policy explicitly allows.

        Returns the last attempt's record. Never raises for a failing tool --
        exhaustion is reported as that record plus attempts().
        """
        if not isinstance(plan, LLMToolInvocationPlan):
            raise TypeError(
                f"Cannot execute something that is not an LLMToolInvocationPlan: {plan!r}."
            )

        limit = self._policy.attempt_limit
        retry_policy = self._policy.as_retry_policy()

        seen_ids = []
        delays = []
        record = None

        for attempt in range(1, limit + 1):
            record = self._run_once(plan, subject, timeout)
            seen_ids.append(record.execution_id)

            # One logical call, one attempt count -- reachable by any of the
            # execution ids the attempts produced.
            self._record_attempt(seen_ids, attempt, delays)

            if self._audit_service is not None:
                self._audit_service.record_execution(record)

            if record.status == SUCCEEDED:
                return record

            # A gate's refusal, or a cancellation, ends this immediately --
            # before the policy is even consulted.
            if record.status in NEVER_RETRYABLE_STATUSES:
                return record

            if not self.should_retry(record):
                return record

            if attempt >= limit:
                return record

            # The codebase's one backoff schedule, not a second one.
            delay = LLMRetryService.compute_backoff(retry_policy, attempt)
            delays.append(delay)
            self._record_attempt(seen_ids, attempt, delays)
            if delay:
                self._sleep(delay)

        return record
