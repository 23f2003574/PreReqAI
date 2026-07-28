from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersion:
    """
    Immutable record of how a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding selects the profile version it resolves to.

    The binding version is a value object only. It performs no
    resolution, pinning, or switching. Resolution, pinning, and
    switching are the responsibility of a binding version service.

    Attributes:
        binding_id: The identifier of the binding this selection
            applies to
        version_selector: Either the literal string "latest", to
            automatically track the bound profile's latest released
            version, or a specific pinned version identifier
        resolved_version: The version identifier resolved for a
            pinned selector, or None for a "latest" selector, whose
            resolution is computed dynamically at resolve time
    """

    binding_id: str

    version_selector: str

    resolved_version: (
        str | None
    )
