from dataclasses import dataclass, field

from ..retry import InvalidRetryPolicyError, LLMRetryPolicy, TransientLLMError
from ..tool_execution import TIMED_OUT

# Statuses that mean the call never reached the tool because a gate refused
# it. Retrying one would just re-run the same refusal, and worse, would treat
# an authorization or validation decision as a transient blip. Never retried,
# whatever a policy says.
NEVER_RETRYABLE_STATUSES = frozenset({"DENIED", "REJECTED", "CANCELLED"})


@dataclass(frozen=True)
class LLMToolRetryPolicy:
    """How many times a failing tool call may be retried, and how long between.

    The tool-calling counterpart of the existing LLMRetryPolicy, and
    deliberately convertible to one (see as_retry_policy): max_attempts and
    backoff carry exactly the meaning they already have there, validation
    defers to that policy's own validate(), and the delay schedule is
    LLMRetryService.compute_backoff -- so there is one exponential-backoff
    definition in the codebase, not two.

    Attributes:
        max_attempts: Total attempts, including the first. 1 disables retrying
        backoff: Base delay in seconds; attempt N waits backoff * 2**(N-1),
            the schedule LLMRetryService already applies
        retryable_errors: What may be retried, stated explicitly. Entries are
            either exception classes (matched against a failing tool's own
            exception) or execution status strings such as TIMED_OUT. The
            default matches the existing retry service's rule -- only
            TransientLLMError -- so nothing is retried by accident
        enabled: A disabled policy allows exactly one attempt, the same way
            LLMRetryService treats a disabled LLMRetryPolicy
    """

    policy_id: str = "default"
    max_attempts: int = 3
    backoff: float = 0.0
    retryable_errors: tuple = (TransientLLMError,)
    enabled: bool = True

    def __post_init__(self):
        # Reuse the existing policy's validation rather than restating it.
        self.as_retry_policy().validate()

        if not isinstance(self.retryable_errors, tuple):
            raise InvalidRetryPolicyError("retryable_errors must be a tuple")

        for entry in self.retryable_errors:
            is_exception = isinstance(entry, type) and issubclass(entry, BaseException)
            if not is_exception and not isinstance(entry, str):
                raise InvalidRetryPolicyError(
                    "each retryable_errors entry must be an exception class or a "
                    f"status string, got {entry!r}"
                )
            if isinstance(entry, str) and entry in NEVER_RETRYABLE_STATUSES:
                raise InvalidRetryPolicyError(
                    f"{entry} can never be retryable: it means a gate refused the "
                    "call, not that the tool failed"
                )

    def as_retry_policy(self) -> LLMRetryPolicy:
        """This policy as the codebase's existing LLMRetryPolicy."""
        return LLMRetryPolicy(
            policy_id=self.policy_id,
            max_attempts=self.max_attempts,
            backoff_seconds=self.backoff,
            enabled=self.enabled,
        )

    @property
    def attempt_limit(self) -> int:
        """Attempts actually permitted -- one when disabled, as LLMRetryService does."""
        return self.max_attempts if self.enabled else 1


DEFAULT_POLICY = LLMToolRetryPolicy(
    policy_id="tool-default",
    max_attempts=3,
    backoff=0.0,
    retryable_errors=(TransientLLMError, TIMED_OUT),
)
