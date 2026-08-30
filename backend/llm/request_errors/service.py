from datetime import datetime, timezone

from ..audit import LLMRequestAudit
from ..budget import BudgetExceededError
from ..provider import UnsupportedModelError, UnsupportedOperationError
from ..retry import PermanentLLMError, RetryExhaustedError, TransientLLMError
from ..routing import NoEligibleModelError
from .models import UNKNOWN, LLMRequestErrorMetric

# The curated set of exception types this repository's own LLM layer
# actually raises for a request attempt (backend.llm.provider's model/
# operation mismatches, backend.llm.retry's transient/permanent/exhausted
# outcomes, backend.llm.routing's no-eligible-route, backend.llm.budget's
# limit, and LLMRequest.validate()'s plain ValueError) -- mapped to a
# stable label and whether retrying the same request could plausibly help.
# Anything else classifies as UNKNOWN rather than being guessed at.
KNOWN_ERRORS = {
    TransientLLMError: ("TRANSIENT", True),
    PermanentLLMError: ("PERMANENT", False),
    RetryExhaustedError: ("RETRY_EXHAUSTED", False),
    UnsupportedModelError: ("UNSUPPORTED_MODEL", False),
    UnsupportedOperationError: ("UNSUPPORTED_OPERATION", False),
    NoEligibleModelError: ("NO_ELIGIBLE_MODEL", False),
    BudgetExceededError: ("BUDGET_EXCEEDED", False),
    ValueError: ("VALIDATION", False),
}


def classify(error: Exception):
    """(error_type, retryable) for an exception actually raised by the LLM layer."""
    return KNOWN_ERRORS.get(type(error), (UNKNOWN, False))


class UnknownRequestErrorMetricError(KeyError):
    """Raised when looking up a request_id with no recorded error."""


class LLMRequestErrorService:
    """Normalizes an LLM request's failure into a stable, deterministic classification.

    Reuses backend.llm.audit.LLMRequestAudit for request_id/provider/model
    identity -- exactly as backend.llm.request_latency does -- and classifies
    whatever exception the caller actually caught from the existing
    provider/retry/routing/budget layer. No second error-reporting system:
    this only labels what already happened.
    """

    def __init__(self):
        self._errors = {}
        self._by_type = {}

    def record(self, request: LLMRequestAudit, error: Exception) -> LLMRequestErrorMetric:
        error_type, retryable = classify(error)

        metric = LLMRequestErrorMetric(
            request_id=request.request_id,
            provider=request.provider,
            model=request.model,
            error_type=error_type,
            retryable=retryable,
            recorded_at=datetime.now(timezone.utc),
        )
        metric.validate()

        self._errors[request.request_id] = metric
        self._by_type.setdefault(error_type, []).append(metric.request_id)
        return metric

    def get(self, request_id: str) -> LLMRequestErrorMetric:
        try:
            return self._errors[request_id]
        except KeyError:
            raise UnknownRequestErrorMetricError(request_id)

    def records(self, scope: str = None) -> tuple:
        """Every recorded error, or just scope's if it names one request_id.

        Unlike get(), a scope with nothing recorded yields an empty tuple
        rather than raising.
        """
        if scope is None:
            return tuple(self._errors.values())
        metric = self._errors.get(scope)
        return (metric,) if metric is not None else ()

    def aggregate(self, provider: str, model: str) -> dict:
        """Deterministic error stats for one provider/model pair."""
        matches = [
            metric
            for metric in self._errors.values()
            if metric.provider == provider and metric.model == model
        ]

        error_type_counts = {}
        for metric in matches:
            error_type_counts[metric.error_type] = error_type_counts.get(metric.error_type, 0) + 1

        return {
            "provider": provider,
            "model": model,
            "count": len(matches),
            "retryable_count": sum(1 for metric in matches if metric.retryable),
            "error_type_counts": error_type_counts,
        }

    def by_type(self, error_type: str) -> list:
        """Every recorded metric of one error_type, across all providers/models."""
        return [self._errors[request_id] for request_id in self._by_type.get(error_type, [])]
