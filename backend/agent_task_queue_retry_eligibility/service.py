from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.agent_failure_handling import LLMAgentFailureService, RETRYABLE
from backend.agent_task_queue_dead_letter import LLMAgentTaskDeadLetterService
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService, UnknownAgentTaskError
from backend.agent_task_queue import InvalidQueueEntryError
from backend.agent_task_readiness import LLMAgentTaskReadinessService
from backend.llm.retry import LLMRetryPolicy, LLMRetryService

from .models import RetryEligibilityResult


class LLMAgentTaskQueueRetryEligibilityService:
    """Decides whether a failed/blocked task_id may currently return to
    normal queue processing -- never a second retry engine of its own
    (Rule: "Do not build a second retry engine"): every rule this
    service evaluates is read from an existing record or delegated to
    an existing service; this class holds no attempt counters, backoff
    schedules, or classification logic of its own.

    Rules are checked in the following order, the first blocking one
    winning (reason names exactly which):
      1. dead-letter status (Commit #8's own
         backend.agent_task_queue_dead_letter.LLMAgentTaskDeadLetterService.get())
         -- checked first and never overridden by anything below (Rule:
         "Never override dead-letter or policy decisions"): a
         dead-lettered task_id is ineligible regardless of how healthy
         its own attempt count or backoff window looks.
      2. task is actually retryable / failure classification -- when a
         backend.agent_failure_handling.LLMAgentFailureService was
         supplied *and* task_id's own AgentTask.definition names an
         execution_id/step_id, that service's own can_continue() is
         the authoritative answer (Rule: reuse "failure classification"
         exactly as Commit #... backend.agent_failure_handling already
         computes it, never a second copy). Otherwise, falls back to
         an explicit task.definition["retryable"] marker if the caller
         set one; absent either, this check simply does not block (no
         evidence either way -- Rule: "Missing retry metadata must
         produce an explicit result, not an invented default" means
         this is reported via attempt_count/remaining_attempts/
         next_eligible_at all reading None, never treated as an
         invented reason to block).
      3. retry/attempt limit -- task.definition["attempt_count"] vs
         ["max_attempts"], both caller-supplied (see this class's own
         __init__ for the full well-known-key vocabulary this reads).
      4. retry delay/backoff -- task.definition["next_eligible_at"] if
         given directly, else derived from ["last_attempt_at"] +
         ["retry_policy"] (an actual backend.llm.retry.LLMRetryPolicy,
         reused verbatim) via that same module's own
         LLMRetryService.compute_backoff() -- Rule: "Reuse existing
         retry/backoff semantics if present," not a second formula.
      5. current readiness -- Commit #1's own
         readiness_service.check(task_id), which already folds in
         "relevant task/agent policies" as one of its own checks (see
         that service's own docstring's "policy" check) -- never a
         second policy evaluation here.

    task.definition is exactly Commit #1's own AgentTask.definition:
    an opaque, caller-supplied dict this service reads well-known keys
    out of, the same "reading well-known keys out of it is this
    service's own business, never Commit #1's" convention
    backend.agent_task_readiness.LLMAgentTaskReadinessService already
    established for its own "plan_id"/"requires_context" keys. None of
    these keys are invented persistence of this service's own -- they
    live exactly where Commit #1 already lets a caller attach whatever
    a task needs, and if a caller never sets any of them, that is
    exactly the "missing retry metadata" case Rule requires this
    service to report explicitly rather than paper over.

    Well-known task.definition keys this service reads:
      - "retryable" (bool): an explicit non-retryable marker (fallback
        only -- see rule 2 above)
      - "attempt_count" (int): attempts already used
      - "max_attempts" (int): the retry ceiling
      - "last_attempt_at" (datetime): when the most recent attempt
        happened
      - "retry_policy" (backend.llm.retry.LLMRetryPolicy): used with
        attempt_count/last_attempt_at to derive next_eligible_at
      - "next_eligible_at" (datetime): a directly caller-supplied
        override, taking precedence over any policy-derived value
      - "execution_id"/"step_id" (str): only consulted when a
        failure_service was supplied to __init__

    dead_letter_required is purely advisory (Rule: "Read-only; do not
    enqueue or retry the task" extends here to never dead-lettering
    anything itself either): True exactly when attempts are exhausted
    and task_id is not already dead-lettered.
    """

    def __init__(
        self,
        lifecycle_service: LLMAgentTaskLifecycleService,
        readiness_service: LLMAgentTaskReadinessService,
        dead_letter_service: LLMAgentTaskDeadLetterService,
        failure_service: LLMAgentFailureService = None,
    ):
        """
        Args:
            lifecycle_service: The exact Commit #1
                LLMAgentTaskLifecycleService instance holding task_id's
                own AgentTask record -- required, never defaulted.
            readiness_service: The exact Commit #1
                LLMAgentTaskReadinessService instance -- required, so
                "current readiness" (and the policy check it already
                includes) always means the same thing here as
                elsewhere in this series.
            dead_letter_service: The exact Commit #8
                LLMAgentTaskDeadLetterService instance -- required, so
                dead-letter status is read from the one real store.
            failure_service: Optional
                backend.agent_failure_handling.LLMAgentFailureService --
                when given, enables the richer, plan-execution-aware
                "failure classification" check (rule 2) for a task_id
                whose own definition names an execution_id/step_id.
                Omit when no plan execution is associated with this
                queue's own tasks; the simpler
                task.definition["retryable"] fallback still applies.
        """
        self._lifecycle_service = lifecycle_service
        self._readiness_service = readiness_service
        self._dead_letter_service = dead_letter_service
        self._failure_service = failure_service

    def check(self, task_id: str, now: Optional[datetime] = None) -> RetryEligibilityResult:
        """Evaluate every applicable rule for task_id, in the order
        this class's own docstring lists, stopping at the first
        blocking one.

        Raises:
            InvalidQueueEntryError: If task_id is missing or blank, or
                now is given and is not a datetime
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidQueueEntryError("task_id is required and must be a non-empty string")
        now = self._resolve_now(now)

        try:
            task = self._lifecycle_service.get(task_id)
        except UnknownAgentTaskError:
            return RetryEligibilityResult(task_id=task_id, eligible=False, reason=f"task {task_id!r} does not exist")

        definition = task.definition if isinstance(task.definition, dict) else {}
        attempt_count = definition.get("attempt_count")
        max_attempts = definition.get("max_attempts")
        remaining_attempts = (
            max(0, max_attempts - attempt_count)
            if isinstance(attempt_count, int) and isinstance(max_attempts, int)
            else None
        )
        next_eligible_at = self._compute_next_eligible_at(definition, attempt_count)

        already_dead_lettered = self._dead_letter_service.get(task_id) is not None
        if already_dead_lettered:
            return RetryEligibilityResult(
                task_id=task_id,
                eligible=False,
                reason="task is already dead-lettered",
                attempt_count=attempt_count,
                remaining_attempts=remaining_attempts,
                next_eligible_at=next_eligible_at,
                dead_letter_required=False,
            )

        retryable, classification_reason = self._classify(task, definition)
        if retryable is False:
            return RetryEligibilityResult(
                task_id=task_id,
                eligible=False,
                reason=classification_reason,
                attempt_count=attempt_count,
                remaining_attempts=remaining_attempts,
                next_eligible_at=next_eligible_at,
                dead_letter_required=True,
            )

        if remaining_attempts is not None and remaining_attempts <= 0:
            return RetryEligibilityResult(
                task_id=task_id,
                eligible=False,
                reason=f"retry limit reached ({attempt_count}/{max_attempts} attempts used)",
                attempt_count=attempt_count,
                remaining_attempts=0,
                next_eligible_at=next_eligible_at,
                dead_letter_required=True,
            )

        if next_eligible_at is not None and now < next_eligible_at:
            return RetryEligibilityResult(
                task_id=task_id,
                eligible=False,
                reason=f"backoff window has not elapsed (eligible again at {next_eligible_at.isoformat()})",
                attempt_count=attempt_count,
                remaining_attempts=remaining_attempts,
                next_eligible_at=next_eligible_at,
            )

        readiness = self._readiness_service.check(task_id)
        if not readiness.ready:
            return RetryEligibilityResult(
                task_id=task_id,
                eligible=False,
                reason="; ".join(readiness.blocking_reasons),
                attempt_count=attempt_count,
                remaining_attempts=remaining_attempts,
                next_eligible_at=next_eligible_at,
            )

        return RetryEligibilityResult(
            task_id=task_id,
            eligible=True,
            reason="eligible for retry",
            attempt_count=attempt_count,
            remaining_attempts=remaining_attempts,
            next_eligible_at=next_eligible_at,
            dead_letter_required=False,
        )

    def _classify(self, task, definition: dict):
        """(retryable, reason). retryable is True/False for a definite
        answer, or None when nothing -- neither a wired failure_service
        with a real execution/step link, nor an explicit "retryable"
        marker -- says anything at all (Rule: "Missing retry metadata
        must produce an explicit result, not an invented default": None
        here never blocks by itself)."""
        execution_id = definition.get("execution_id")
        step_id = definition.get("step_id")
        if self._failure_service is not None and execution_id and step_id:
            classification = self._failure_service.classify(execution_id, step_id)
            retryable = classification.category == RETRYABLE
            if not retryable:
                return False, f"failure classification is {classification.category!r}: {classification.reason}"
            return True, classification.reason

        marker = definition.get("retryable")
        if marker is False:
            return False, "task is marked as not retryable"
        return None, "eligible for retry"

    @staticmethod
    def _compute_next_eligible_at(definition: dict, attempt_count) -> Optional[datetime]:
        explicit = definition.get("next_eligible_at")
        if isinstance(explicit, datetime):
            return explicit

        last_attempt_at = definition.get("last_attempt_at")
        retry_policy = definition.get("retry_policy")
        if (
            isinstance(last_attempt_at, datetime)
            and isinstance(retry_policy, LLMRetryPolicy)
            and isinstance(attempt_count, int)
            and attempt_count > 0
        ):
            delay = LLMRetryService.compute_backoff(retry_policy, attempt_count)
            return last_attempt_at + timedelta(seconds=delay)

        return None

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidQueueEntryError("now must be a datetime when given")
        return now
