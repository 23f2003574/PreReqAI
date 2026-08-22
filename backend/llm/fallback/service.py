from ..budget import BudgetExceededError, LLMBudgetService
from ..routing import LLMModelRoutingService, NoEligibleModelError
from .models import LLMFallbackPolicy


class UnknownFallbackRequestError(KeyError):
    """Raised when history()/fallback() is used before resolve() started a chain."""


class NoFallbackPolicyError(KeyError):
    """Raised when no configured LLMFallbackPolicy applies to a request."""


class LLMFallbackRoutingService:
    """Automatically switches to an eligible fallback provider/model on failure.

    Eligibility is delegated entirely to Commit #3's LLMModelRoutingService,
    which in turn reuses Commit #2's LLMProviderConfigService (so disabled
    providers are skipped) and enforces capability/cost/latency requirements.
    An optional Commit #8 LLMBudgetService additionally skips a candidate
    that would exceed a scope's remaining budget.
    """

    def __init__(
        self,
        routing_service: LLMModelRoutingService,
        budget_service: LLMBudgetService = None,
    ):
        self._routing_service = routing_service
        self._budget_service = budget_service
        self._policies = {}
        self._history = {}
        self._failed_providers = {}

    def configure(self, policy: LLMFallbackPolicy) -> LLMFallbackPolicy:
        policy.validate()
        self._policies[policy.primary_provider] = policy
        return policy

    def _select_policy(self, request) -> LLMFallbackPolicy:
        if (
            request.preferred_provider is not None
            and request.preferred_provider in self._policies
        ):
            return self._policies[request.preferred_provider]

        if len(self._policies) == 1:
            return next(iter(self._policies.values()))

        raise NoFallbackPolicyError(
            "no LLMFallbackPolicy applies to this request; configure one or set "
            "LLMRouteRequest.preferred_provider to a configured primary_provider"
        )

    @staticmethod
    def _candidate_order(policy: LLMFallbackPolicy) -> list:
        chain = (
            [policy.primary_provider, *policy.fallback_providers]
            if policy.enabled
            else [policy.primary_provider]
        )
        ordered = []
        for provider in chain:
            if provider not in ordered:
                ordered.append(provider)
        return ordered

    def _advance(
        self, request, request_id, policy, budget_scope_id, estimated_tokens, estimated_cost
    ):
        candidates = self._candidate_order(policy)
        failed = self._failed_providers[request_id]
        already_selected = sum(
            1 for entry in self._history[request_id] if entry["outcome"] == "selected"
        )

        ranked = self._routing_service.rank(request)
        eligible_by_provider = {route.provider: route for route in ranked}

        for provider in candidates:
            if provider in failed:
                continue

            if already_selected >= policy.max_attempts:
                break

            route = eligible_by_provider.get(provider)
            if route is None:
                self._history[request_id].append(
                    {"provider": provider, "outcome": "skipped", "reason": "ineligible"}
                )
                continue

            if self._budget_service is not None and budget_scope_id is not None:
                try:
                    self._budget_service.check(budget_scope_id, estimated_tokens, estimated_cost)
                except BudgetExceededError:
                    self._history[request_id].append(
                        {
                            "provider": provider,
                            "outcome": "skipped",
                            "reason": "budget exceeded",
                        }
                    )
                    continue

            self._history[request_id].append({"provider": provider, "outcome": "selected"})
            return route

        raise NoEligibleModelError(
            f"no eligible fallback provider remains for request {request_id!r}"
        )

    def resolve(
        self,
        request,
        request_id: str,
        budget_scope_id: str = None,
        estimated_tokens: int = 0,
        estimated_cost: float = 0.0,
    ):
        policy = self._select_policy(request)
        self._failed_providers[request_id] = set()
        self._history[request_id] = []
        return self._advance(
            request, request_id, policy, budget_scope_id, estimated_tokens, estimated_cost
        )

    def fallback(
        self,
        request,
        request_id: str,
        failed_provider: str,
        budget_scope_id: str = None,
        estimated_tokens: int = 0,
        estimated_cost: float = 0.0,
    ):
        if request_id not in self._history:
            raise UnknownFallbackRequestError(request_id)

        policy = self._select_policy(request)
        self._failed_providers[request_id].add(failed_provider)
        self._history[request_id].append({"provider": failed_provider, "outcome": "failed"})

        return self._advance(
            request, request_id, policy, budget_scope_id, estimated_tokens, estimated_cost
        )

    def history(self, request_id: str) -> list:
        try:
            return list(self._history[request_id])
        except KeyError:
            raise UnknownFallbackRequestError(request_id)
