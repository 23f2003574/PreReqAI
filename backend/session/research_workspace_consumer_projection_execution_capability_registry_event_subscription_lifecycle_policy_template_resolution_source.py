from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionSource(
    str,
    Enum,
):
    """
    Canonical sources from which a consumer projection execution
    capability registry event subscription lifecycle policy
    template resolution can be satisfied.

    This enum only names the possible sources. It performs no
    resolution or lookup logic.
    """

    DIRECT_MATCH = (
        "direct_match"
    )

    DEFAULT_TEMPLATE = (
        "default_template"
    )
