from .models import (
    InvalidConfigurationError,
    LLMProviderConfig,
    MissingCredentialsError,
)


class UnknownProviderError(KeyError):
    """Raised when looking up a provider that has not been registered."""


class ProviderAlreadyRegisteredError(InvalidConfigurationError):
    """Raised when register() is called for a provider that already has a config."""


class LLMProviderConfigService:
    """Central registry of one active LLMProviderConfig per provider."""

    def __init__(self):
        self._configs = {}

    def register(self, config: LLMProviderConfig) -> LLMProviderConfig:
        config.validate()
        if config.provider in self._configs:
            raise ProviderAlreadyRegisteredError(
                f"provider {config.provider!r} is already registered; "
                "use update() to change its configuration"
            )
        self._configs[config.provider] = config
        return config

    def get(self, provider: str) -> LLMProviderConfig:
        try:
            return self._configs[provider]
        except KeyError:
            raise UnknownProviderError(provider)

    def update(self, provider: str, config: LLMProviderConfig) -> LLMProviderConfig:
        self.get(provider)
        if config.provider != provider:
            raise InvalidConfigurationError(
                "config.provider must match the provider being updated"
            )
        config.validate()
        self._configs[provider] = config
        return config

    def enable(self, provider: str) -> LLMProviderConfig:
        config = self.get(provider)
        if not config.api_key_ref:
            raise MissingCredentialsError(
                f"cannot enable provider {provider!r} without an api_key_ref"
            )
        config.enabled = True
        return config

    def disable(self, provider: str) -> LLMProviderConfig:
        config = self.get(provider)
        config.enabled = False
        return config

    def active(self) -> dict:
        """Return the enabled configs available for routing, keyed by provider."""
        return {
            provider: config
            for provider, config in self._configs.items()
            if config.enabled
        }
