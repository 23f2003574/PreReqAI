from ..config import LLMProviderConfigService
from .models import LLMRoute, LLMRouteRequest, ProviderCapabilityProfile


class NoEligibleModelError(Exception):
    """Raised when no enabled provider satisfies a route request."""


class LLMModelRoutingService:
    """Selects the best enabled provider/model for a route request.

    Provider enablement and model selection are delegated to an
    LLMProviderConfigService (Commit #2); capability/cost/latency metadata
    used for ranking is registered here per provider.
    """

    def __init__(self, config_service: LLMProviderConfigService):
        self._config_service = config_service
        self._capability_profiles = {}

    def register_capability_profile(self, provider: str, profile: ProviderCapabilityProfile):
        self._capability_profiles[provider] = profile

    def available(self) -> dict:
        """Enabled provider configs that have a registered capability profile."""
        return {
            provider: config
            for provider, config in self._config_service.active().items()
            if provider in self._capability_profiles
        }

    def _eligible(self, request: LLMRouteRequest) -> list:
        required = frozenset(request.required_capabilities)
        eligible = []

        for provider, config in self.available().items():
            profile = self._capability_profiles[provider]

            if not required <= profile.capabilities:
                continue
            if request.max_cost is not None and profile.cost > request.max_cost:
                continue
            if request.max_latency is not None and profile.latency > request.max_latency:
                continue

            eligible.append((provider, config, profile))

        return eligible

    def _score(self, profile: ProviderCapabilityProfile) -> float:
        score = 1.0
        score += 1.0 / (1.0 + profile.cost)
        score += 1.0 / (1.0 + profile.latency)
        score += 0.1 * len(profile.capabilities)
        return round(score, 6)

    def _reason(self, provider: str, profile: ProviderCapabilityProfile) -> str:
        return (
            f"capabilities={sorted(profile.capabilities)} "
            f"cost={profile.cost} latency={profile.latency}"
        )

    def rank(self, request: LLMRouteRequest) -> list:
        """Return all eligible routes, best first, in a deterministic order."""
        request.validate()

        routes = [
            LLMRoute(
                provider=provider,
                model=config.model,
                score=self._score(profile),
                reason=self._reason(provider, profile),
            )
            for provider, config, profile in self._eligible(request)
        ]

        routes.sort(key=lambda route: (-route.score, route.provider, route.model))
        return routes

    def resolve(self, request: LLMRouteRequest) -> LLMRoute:
        """Return the single best route, honoring an explicit preference."""
        request.validate()

        if request.preferred_provider is not None:
            eligible = {
                provider: (config, profile)
                for provider, config, profile in self._eligible(request)
            }
            match = eligible.get(request.preferred_provider)
            if match is None:
                raise NoEligibleModelError(
                    f"preferred provider {request.preferred_provider!r} is not "
                    "available or does not meet the request's requirements"
                )
            config, profile = match
            return LLMRoute(
                provider=request.preferred_provider,
                model=config.model,
                score=self._score(profile),
                reason=f"explicit preferred_provider={request.preferred_provider!r}",
            )

        routes = self.rank(request)
        if not routes:
            raise NoEligibleModelError(
                f"no enabled provider satisfies task={request.task!r} with "
                f"required_capabilities={sorted(request.required_capabilities)}, "
                f"max_cost={request.max_cost}, max_latency={request.max_latency}"
            )
        return routes[0]
