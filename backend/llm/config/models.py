from dataclasses import dataclass
from typing import Optional

from ..registry import PROVIDERS

_RAW_KEY_PREFIXES = ("sk-", "AIza", "key-")


class InvalidConfigurationError(ValueError):
    """Raised when an LLMProviderConfig fails validation."""


class MissingCredentialsError(InvalidConfigurationError):
    """Raised when an enabled provider config has no credential reference."""


@dataclass
class LLMProviderConfig:
    """Centralized runtime configuration for a single LLM provider."""

    provider: str
    model: str
    endpoint: Optional[str] = None
    api_key_ref: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    enabled: bool = True

    def validate(self):
        if not self.provider or not isinstance(self.provider, str):
            raise InvalidConfigurationError("provider is required")

        if self.provider not in PROVIDERS:
            raise InvalidConfigurationError(
                f"unknown provider {self.provider!r}. Registered providers: "
                f"{sorted(PROVIDERS)}"
            )

        if not self.model or not isinstance(self.model, str):
            raise InvalidConfigurationError("model is required")

        if not (0.0 <= self.temperature <= 2.0):
            raise InvalidConfigurationError(
                "temperature must be between 0.0 and 2.0"
            )

        if self.max_tokens is not None and self.max_tokens <= 0:
            raise InvalidConfigurationError("max_tokens must be a positive integer")

        if self.api_key_ref is not None:
            if not self.api_key_ref.strip():
                raise InvalidConfigurationError(
                    "api_key_ref must not be blank when provided"
                )
            if self.api_key_ref.startswith(_RAW_KEY_PREFIXES):
                raise InvalidConfigurationError(
                    "api_key_ref must reference a stored credential "
                    "(e.g. an env var or secret manager name), not a raw API key"
                )

        if self.enabled and not self.api_key_ref:
            raise MissingCredentialsError(
                f"provider {self.provider!r} is enabled but has no api_key_ref"
            )
