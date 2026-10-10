from datetime import datetime, timezone

from ..audit import LLMRequestAuditService
from ..budget import BudgetExceededError, LLMBudgetService
from ..context import LLMContextService
from ..cost import LLMCostService
from ..fallback import LLMFallbackRoutingService
from ..models import LLMRequest
from ..response_cache import LLMResponseCacheService
from ..retry import LLMRetryService
from ..routing import LLMModelRoutingService, NoEligibleModelError
from ..usage import LLMUsageService
from .models import LLMRequestDecision


class UnknownDecisionError(KeyError):
    """Raised when looking up a request_id with no recorded decision."""


class LLMRequestOrchestrationService:
    """Unifies routing, context, budgets, caching, retries, fallback, usage,
    cost, and auditing into one deterministic LLM request pipeline.

    Every collaborator is an existing service from an earlier commit --
    this service adds no provider-specific behavior of its own, it only
    sequences calls into them in a fixed order:

        build context -> enforce budget -> route -> check cache ->
        (retry, then fallback on failure) -> record usage/cost/audit ->
        return one decision
    """

    def __init__(
        self,
        context_service: LLMContextService,
        routing_service: LLMModelRoutingService,
        providers: dict,
        budget_service: LLMBudgetService = None,
        cache_service: LLMResponseCacheService = None,
        retry_service: LLMRetryService = None,
        fallback_service: LLMFallbackRoutingService = None,
        usage_service: LLMUsageService = None,
        cost_service: LLMCostService = None,
        audit_service: LLMRequestAuditService = None,
    ):
        self._context_service = context_service
        self._routing_service = routing_service
        self._providers = providers
        self._budget_service = budget_service
        self._cache_service = cache_service
        self._retry_service = retry_service
        self._fallback_service = fallback_service
        self._usage_service = usage_service
        self._cost_service = cost_service
        self._audit_service = audit_service
        self._decisions = {}
        self._decision_counter = 0

    def prepare(self, context_id: str) -> dict:
        """Build context first -- the provider-agnostic system/messages payload."""
        return self._context_service.build(context_id)

    def route(
        self,
        route_request,
        request_id: str,
        budget_scope_id: str = None,
        estimated_tokens: int = 0,
        estimated_cost: float = 0.0,
    ):
        """Route only eligible providers/models, preferring fallback ordering if configured."""
        if self._fallback_service is not None:
            return self._fallback_service.resolve(
                route_request, request_id, budget_scope_id, estimated_tokens, estimated_cost
            )
        return self._routing_service.resolve(route_request)

    def _store_decision(
        self, request_id: str, provider, model, cached: bool, allowed: bool, reason: str
    ) -> LLMRequestDecision:
        self._decision_counter += 1
        decision = LLMRequestDecision(
            decision_id=f"decision-{self._decision_counter}",
            request_id=request_id,
            provider=provider,
            model=model,
            cached=cached,
            allowed=allowed,
            reason=reason,
            created_at=datetime.now(timezone.utc),
        )
        self._decisions[request_id] = decision
        return decision

    def execute(
        self,
        route_request,
        request_id: str,
        context_id: str,
        budget_scope_id: str = None,
        estimated_tokens: int = 0,
        estimated_cost: float = 0.0,
        temperature: float = 0.0,
        max_tokens: int = None,
    ):
        """Run the full pipeline; returns (response_or_None, LLMRequestDecision)."""
        built = self.prepare(context_id)

        if self._budget_service is not None and budget_scope_id is not None:
            try:
                self._budget_service.check(budget_scope_id, estimated_tokens, estimated_cost)
            except BudgetExceededError as exc:
                return None, self._store_decision(
                    request_id, None, None, cached=False, allowed=False,
                    reason=f"budget exceeded: {exc}",
                )

        try:
            route = self.route(
                route_request, request_id, budget_scope_id, estimated_tokens, estimated_cost
            )
        except NoEligibleModelError as exc:
            return None, self._store_decision(
                request_id, None, None, cached=False, allowed=False,
                reason=f"no eligible provider: {exc}",
            )

        provider_name = route.provider
        model = route.model
        llm_request = LLMRequest(
            model=model, messages=built["messages"], temperature=temperature, max_tokens=max_tokens
        )
        llm_request.validate()

        if self._cache_service is not None:
            cached_response = self._cache_service.get(llm_request)
            if cached_response is not None:
                decision = self._store_decision(
                    request_id, provider_name, model, cached=True, allowed=True, reason="cache hit"
                )
                return cached_response, decision

        if self._audit_service is not None:
            self._audit_service.start(llm_request, request_id, provider_name)

        response = None
        while True:
            provider_instance = self._providers[provider_name]
            try:
                if self._retry_service is not None:
                    response = self._retry_service.execute(
                        llm_request, request_id, provider_instance, scope_id=request_id
                    )
                else:
                    response = provider_instance.complete(llm_request)
            except Exception as exc:
                if self._fallback_service is None:
                    if self._audit_service is not None:
                        self._audit_service.complete(request_id, status="failed")
                    return None, self._store_decision(
                        request_id, provider_name, model, cached=False, allowed=False,
                        reason=f"provider failed: {exc}",
                    )

                try:
                    next_route = self._fallback_service.fallback(
                        route_request,
                        request_id,
                        failed_provider=provider_name,
                        budget_scope_id=budget_scope_id,
                        estimated_tokens=estimated_tokens,
                        estimated_cost=estimated_cost,
                    )
                except NoEligibleModelError as fallback_exc:
                    if self._audit_service is not None:
                        self._audit_service.complete(request_id, status="failed")
                    return None, self._store_decision(
                        request_id, provider_name, model, cached=False, allowed=False,
                        reason=f"all providers exhausted: {fallback_exc}",
                    )

                provider_name = next_route.provider
                model = next_route.model
                llm_request = LLMRequest(
                    model=model,
                    messages=built["messages"],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if self._audit_service is not None:
                    self._audit_service.record_attempt(request_id, provider_name, model)
                continue
            else:
                break

        if self._cache_service is not None:
            self._cache_service.set(llm_request, response)

        if self._usage_service is not None:
            self._usage_service.record(response, request_id, provider_name)

        if self._budget_service is not None and budget_scope_id is not None:
            total_tokens = (response.usage or {}).get("total_tokens", 0)
            self._budget_service.consume(budget_scope_id, tokens=total_tokens, cost=0.0)

        if self._audit_service is not None:
            self._audit_service.complete(request_id, status="succeeded")

        decision = self._store_decision(
            request_id, provider_name, model, cached=False, allowed=True, reason="succeeded"
        )
        return response, decision

    def decision(self, request_id: str) -> LLMRequestDecision:
        try:
            return self._decisions[request_id]
        except KeyError:
            raise UnknownDecisionError(request_id)
