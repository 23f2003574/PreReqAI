from abc import ABC, abstractmethod

from .models import LLMRequest, LLMResponse


class UnsupportedModelError(Exception):
    """Raised when a request names a model the provider does not serve."""


class UnsupportedOperationError(Exception):
    """Raised when a provider does not implement a given operation."""


class LLMProvider(ABC):
    """Provider-neutral interface every LLM adapter must implement."""

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a single normalized LLMResponse for the request."""

    @abstractmethod
    def stream(self, request: LLMRequest):
        """Yield response content incrementally for the request."""

    @abstractmethod
    def models(self) -> list:
        """Return the list of model identifiers this provider supports."""

    def _check_model_supported(self, request: LLMRequest):
        request.validate()
        if request.model not in self.models():
            raise UnsupportedModelError(
                f"{request.model!r} is not supported by "
                f"{self.__class__.__name__}. Available models: {self.models()}"
            )
