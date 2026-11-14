"""The seam between PreReqAI's tutor and a text-generation provider: a provider turns a system prompt and a user prompt into text, and
reports every failure as a ProviderError with a kind the tutor can show. The tutor owns the prompts, the validation and the fallback."""
import math
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

PROVIDERS = ("rule-based", "gemini")
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"  # a Flash-class model Google documents as stable; PREREQAI_GEMINI_MODEL overrides it (check Google's current model list)
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_OUTPUT_TOKENS = 600


class ProviderError(Exception):
    """A provider could not produce an answer. `kind`: not_configured | rate_limit | timeout | auth | provider | bad_response. The message never
    contains a credential or the provider's raw error text."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


class TutorProvider(ABC):
    name = "provider"
    model = ""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """The model's text for the prompts; ProviderError for any failure. No tools or function calls are offered to the model."""


def _positive_float(value, default):
    try:
        number = float(str(value).strip())
    except ValueError:
        return default
    return number if math.isfinite(number) and number > 0 else default


@dataclass(frozen=True)
class TutorConfig:
    """Read from the environment on every question, so a deployment is configured with variables only. The Gemini credential is read from
    GEMINI_API_KEY by the provider itself and never appears here. Without PREREQAI_TUTOR_PROVIDER=gemini the built-in tutor is used, even if a key exists."""
    provider: str = "rule-based"
    model: str = DEFAULT_GEMINI_MODEL
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    problem: str = ""  # a misconfiguration to tell the learner about (the built-in tutor is used meanwhile)

    @classmethod
    def from_env(cls):
        env = os.environ
        wanted = env.get("PREREQAI_TUTOR_PROVIDER", "").strip().lower() or "rule-based"
        problem = "" if wanted in PROVIDERS else f"PREREQAI_TUTOR_PROVIDER={wanted!r} is not one of {', '.join(PROVIDERS)}, so the built-in tutor is used."
        try:
            tokens = int(env.get("PREREQAI_TUTOR_MAX_OUTPUT_TOKENS", "").strip() or DEFAULT_MAX_OUTPUT_TOKENS)
        except ValueError:
            tokens = DEFAULT_MAX_OUTPUT_TOKENS
        return cls(provider=wanted if not problem else "rule-based",
                   model=env.get("PREREQAI_GEMINI_MODEL", "").strip() or DEFAULT_GEMINI_MODEL,
                   timeout_seconds=_positive_float(env.get("PREREQAI_TUTOR_TIMEOUT_SECONDS", ""), DEFAULT_TIMEOUT_SECONDS),
                   max_output_tokens=tokens if 64 <= tokens <= 4096 else DEFAULT_MAX_OUTPUT_TOKENS, problem=problem)
