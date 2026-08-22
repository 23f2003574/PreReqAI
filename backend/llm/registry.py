from .adapters import GeminiProvider, LocalLLMProvider, OpenAIProvider

PROVIDERS = {
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "local": LocalLLMProvider,
}


def get_provider(name: str, **kwargs):
    """Instantiate the LLMProvider adapter registered under `name`."""
    try:
        provider_cls = PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown LLM provider {name!r}. Available providers: "
            f"{sorted(PROVIDERS)}"
        )
    return provider_cls(**kwargs)
