from dataclasses import dataclass


class InvalidRetryPolicyError(ValueError):
    """Raised when an LLMRetryPolicy fails validation."""


@dataclass(frozen=True)
class LLMRetryPolicy:
    """Immutable policy: how many attempts, and the backoff between them."""

    policy_id: str
    max_attempts: int
    backoff_seconds: float
    enabled: bool = True

    def validate(self):
        if not self.policy_id or not isinstance(self.policy_id, str):
            raise InvalidRetryPolicyError("policy_id is required")

        if (
            not isinstance(self.max_attempts, int)
            or isinstance(self.max_attempts, bool)
            or self.max_attempts < 1
        ):
            raise InvalidRetryPolicyError("max_attempts must be a positive integer")

        if self.backoff_seconds < 0:
            raise InvalidRetryPolicyError("backoff_seconds must not be negative")
