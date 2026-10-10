import pytest

from backend.llm.config import (
    InvalidConfigurationError,
    LLMProviderConfig,
    LLMProviderConfigService,
    MissingCredentialsError,
    ProviderAlreadyRegisteredError,
    UnknownProviderError,
)


def make_config(**overrides):
    fields = {
        "provider": "openai",
        "model": "gpt-4o",
        "api_key_ref": "OPENAI_API_KEY",
    }
    fields.update(overrides)
    return LLMProviderConfig(**fields)


def test_register_and_get():
    service = LLMProviderConfigService()
    config = make_config()

    registered = service.register(config)

    assert registered is config
    assert service.get("openai") is config

    with pytest.raises(ProviderAlreadyRegisteredError):
        service.register(make_config())

    with pytest.raises(UnknownProviderError):
        service.get("gemini")


def test_update():
    service = LLMProviderConfigService()
    service.register(make_config(model="gpt-4o"))

    updated = service.update("openai", make_config(model="gpt-4o-mini"))

    assert updated.model == "gpt-4o-mini"
    assert service.get("openai").model == "gpt-4o-mini"

    with pytest.raises(UnknownProviderError):
        service.update("gemini", make_config(provider="gemini", api_key_ref="GEMINI_KEY"))

    with pytest.raises(InvalidConfigurationError):
        service.update("openai", make_config(provider="gemini", api_key_ref="GEMINI_KEY"))


def test_enable_disable():
    service = LLMProviderConfigService()
    service.register(make_config())

    disabled = service.disable("openai")
    assert disabled.enabled is False
    assert "openai" not in service.active()

    enabled = service.enable("openai")
    assert enabled.enabled is True
    assert "openai" in service.active()

    with pytest.raises(UnknownProviderError):
        service.enable("local")


def test_default_selection():
    service = LLMProviderConfigService()
    service.register(make_config(provider="openai", api_key_ref="OPENAI_API_KEY"))
    service.register(
        make_config(provider="gemini", model="gemini-1.5-pro", api_key_ref="GEMINI_KEY")
    )
    service.register(
        LLMProviderConfig(
            provider="local", model="llama3", api_key_ref=None, enabled=False
        )
    )

    active = service.active()

    assert set(active) == {"openai", "gemini"}
    assert active["openai"].provider == "openai"
    assert all(config.provider == provider for provider, config in active.items())


def test_missing_credentials():
    with pytest.raises(MissingCredentialsError):
        LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref=None).validate()

    service = LLMProviderConfigService()
    service.register(
        LLMProviderConfig(
            provider="local", model="llama3", api_key_ref=None, enabled=False
        )
    )

    with pytest.raises(MissingCredentialsError):
        service.enable("local")


def test_invalid_configuration():
    with pytest.raises(InvalidConfigurationError):
        LLMProviderConfig(provider="not-a-provider", model="gpt-4o").validate()

    with pytest.raises(InvalidConfigurationError):
        LLMProviderConfig(provider="openai", model="").validate()

    with pytest.raises(InvalidConfigurationError):
        make_config(temperature=9.0).validate()

    with pytest.raises(InvalidConfigurationError):
        make_config(max_tokens=-1).validate()

    with pytest.raises(InvalidConfigurationError):
        make_config(api_key_ref="sk-live-raw-secret-value").validate()
