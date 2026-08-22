import time

from ..budget import LLMBudgetService
from ..response_cache import LLMResponseCacheService
from .models import InvalidRetryPolicyError, LLMRetryPolicy


class TransientLLMError(Exception):
    """A retryable, transient provider failure (timeouts, rate limits, 5xx, etc.)."""


class PermanentLLMError(Exception):
    """A non-retryable provider failure. Never retried."""


class RetryExhaustedError(Exception):
    """Raised when every configured attempt has been used without success."""


DEFAULT_POLICY = LLMRetryPolicy(
    policy_id="default", max_attempts=3, backoff_seconds=1.0, enabled=True
)


class LLMRetryService:
    """Retries transient LLM provider failures with exponential backoff.

    Reuses Commit #1's LLMProvider/LLMRequest, Commit #9's
    LLMResponseCacheService (a cache hit short-circuits execution entirely,
    so a request that already succeeded is never duplicated), and Commit
    #8's LLMBudgetService (checked before attempting, consumed on success).
    Only TransientLLMError is retried; everything else -- including
    LLMRequest.validate() failures and Commit #1's UnsupportedModelError --
    fails immediately without consuming a retry.
    """

    def __init__(
        self,
        cache_service: LLMResponseCacheService = None,
        budget_service: LLMBudgetService = None,
    ):
        self._cache_service = cache_service
        self._budget_service = budget_service
        self._policies = {}
        self._attempts = {}
        self._next_retry_delays = {}

    def configure(self, scope_id, policy: LLMRetryPolicy) -> LLMRetryPolicy:
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidRetryPolicyError("scope_id is required")

        policy.validate()
        self._policies[scope_id] = policy
        return policy

    @staticmethod
    def compute_backoff(policy: LLMRetryPolicy, attempt: int) -> float:
        """Delay in seconds before the next try, given `attempt` just failed."""
        return policy.backoff_seconds * (2 ** (attempt - 1))

    def attempts(self, request_id: str) -> int:
        return self._attempts.get(request_id, 0)

    def next_retry(self, request_id: str):
        """The backoff delay (seconds) used before the most recent retry, or None."""
        return self._next_retry_delays.get(request_id)

    def execute(
        self,
        request,
        request_id: str,
        provider,
        scope_id: str = None,
        budget_scope_id: str = None,
        estimated_tokens: int = 0,
        estimated_cost: float = 0.0,
    ):
        if self._cache_service is not None:
            cached = self._cache_service.get(request)
            if cached is not None:
                return cached

        request.validate()

        if self._budget_service is not None and budget_scope_id is not None:
            self._budget_service.check(
                budget_scope_id,
                estimated_tokens=estimated_tokens,
                estimated_cost=estimated_cost,
            )

        policy = self._policies.get(scope_id, DEFAULT_POLICY)
        max_attempts = policy.max_attempts if policy.enabled else 1

        self._attempts[request_id] = 0
        self._next_retry_delays.pop(request_id, None)

        last_error = None
        for attempt in range(1, max_attempts + 1):
            self._attempts[request_id] = attempt

            try:
                response = provider.complete(request)
            except TransientLLMError as exc:
                last_error = exc
                if attempt >= max_attempts:
                    break
                delay = self.compute_backoff(policy, attempt)
                self._next_retry_delays[request_id] = delay
                time.sleep(delay)
                continue

            if self._cache_service is not None:
                self._cache_service.set(request, response)

            if self._budget_service is not None and budget_scope_id is not None:
                total_tokens = (response.usage or {}).get("total_tokens", 0)
                self._budget_service.consume(budget_scope_id, tokens=total_tokens, cost=0.0)

            return response

        raise RetryExhaustedError(
            f"request {request_id!r} exhausted {max_attempts} attempt(s)"
        ) from last_error
