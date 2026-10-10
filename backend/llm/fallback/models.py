from dataclasses import dataclass


class InvalidFallbackPolicyError(ValueError):
    """Raised when an LLMFallbackPolicy fails validation."""


@dataclass(frozen=True)
class LLMFallbackPolicy:
    """Immutable ordered provider preference: try primary, then each fallback in order."""

    policy_id: str
    primary_provider: str
    fallback_providers: tuple
    max_attempts: int = 3
    enabled: bool = True

    def validate(self):
        if not self.policy_id or not isinstance(self.policy_id, str):
            raise InvalidFallbackPolicyError("policy_id is required")

        if not self.primary_provider or not isinstance(self.primary_provider, str):
            raise InvalidFallbackPolicyError("primary_provider is required")

        if any(
            not provider or not isinstance(provider, str)
            for provider in self.fallback_providers
        ):
            raise InvalidFallbackPolicyError(
                "fallback_providers must contain only non-empty provider names"
            )

        if (
            not isinstance(self.max_attempts, int)
            or isinstance(self.max_attempts, bool)
            or self.max_attempts < 1
        ):
            raise InvalidFallbackPolicyError("max_attempts must be a positive integer")
