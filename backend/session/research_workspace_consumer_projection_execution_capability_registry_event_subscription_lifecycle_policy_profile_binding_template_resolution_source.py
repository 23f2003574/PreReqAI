from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource(
    str,
    Enum,
):
    """
    Canonical sources from which a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding template resolution can be satisfied.

    This enum only names the possible sources. It performs no
    resolution or lookup logic.
    """

    REGISTRY = "registry"

    DEFAULT = "default"
