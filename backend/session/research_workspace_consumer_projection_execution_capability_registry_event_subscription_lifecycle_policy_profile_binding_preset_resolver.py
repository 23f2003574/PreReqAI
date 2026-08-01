from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_resolution_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolver:
    """
    Resolves the effective consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    preset, and its eligible member binding templates, for a preset
    identifier, providing a single lookup interface for downstream
    instantiation and deployment components.

    The resolver's responsibility is centralized, deterministic
    resolution of the effective preset and its members for a given
    preset ID, not preset creation, replacement, removal, validation,
    or persistence. It does NOT create presets, mutate a registry,
    validate presets, persist results, log, or publish events. A
    resolver works against any object exposing a `find(preset_id)`
    lookup, such as a binding preset registry service, together with
    a binding template registry exposing `find(template_id)` and an
    activation service exposing `state(template_id)`. Only a binding
    template that is both registered and ACTIVE is included among a
    preset's resolved members; missing and inactive members are
    silently skipped, and members are returned in the order they are
    stored on the preset.

    The resolver is:
    - Stateless: No mutable instance state; the registries and
      default preset it was constructed with are treated as
      read-only
    - Deterministic: Same preset ID and registry state always
      produce the same outcome
    - Side-effect free: Never mutates the preset registry, the
      binding template registry, or the activation service it
      resolves against
    """

    def __init__(
        self,
        preset_registry,
        template_registry,
        activation_service,
        default_preset=None,
    ):
        """
        Args:
            preset_registry: The primary lookup source to resolve
                against. Any object exposing a `find(preset_id)`
                lookup is accepted
            template_registry: The registry used to look up a
                preset's member binding templates. Any object
                exposing a `find(template_id)` lookup is accepted
            activation_service: The service used to check whether a
                member binding template is eligible to participate in
                resolution. Any object exposing `state(template_id)`
                is accepted
            default_preset: An optional preset to fall back to when
                the registry has no preset for the preset ID

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError:
                If the preset registry, template registry, or
                activation service is None
        """

        if preset_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError(
                "Cannot resolve binding presets against a None preset registry."
            )

        if template_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError(
                "Cannot resolve binding presets against a None template registry."
            )

        if activation_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError(
                "Cannot resolve binding presets against a None activation service."
            )

        self._preset_registry = preset_registry
        self._template_registry = template_registry
        self._activation_service = activation_service
        self._default_preset = default_preset

    def resolve(
        self,
        preset_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResult:
        """
        Resolve the effective binding preset, and its eligible member
        binding templates, for a preset ID.

        The preset registry is consulted first. If it has no preset
        for the preset ID and a default preset was configured, the
        default preset is used instead.

        Returns:
            An immutable resolution result. If no preset is found in
            any configured source, resolved is False, preset is None,
            templates is empty, and source is None

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError:
                If the preset ID is None or blank, or the resolved
                preset's membership is corrupted
        """

        self._validate_preset_id(preset_id)

        preset = self._preset_registry.find(preset_id)
        source = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource.REGISTRY

        if preset is None:
            preset = self._default_preset
            source = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionSource.DEFAULT

        if preset is None:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResult(
                preset=None,
                templates=(),
                resolved=False,
                source=None,
            )

        self._validate_preset_membership(preset)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolutionResult(
            preset=preset,
            templates=self._resolve_members(preset),
            resolved=True,
            source=source,
        )

    def resolve_or_raise(
        self,
        preset_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset:
        """
        Resolve the effective binding preset for a preset ID, raising
        if it cannot be resolved.

        Returns:
            The resolved preset

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError:
                If the preset ID is None or blank, or no preset could
                be resolved for it
        """

        result = self.resolve(preset_id)

        if not result.resolved:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError(
                f"Cannot resolve a binding preset for preset ID {preset_id!r}: no preset was found."
            )

        return result.preset

    def contains(self, preset_id: str) -> bool:
        """
        Check whether an effective binding preset can be resolved for
        a preset ID.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError:
                If the preset ID is None or blank
        """

        return self.resolve(preset_id).resolved

    def resolve_templates(self, preset_id: str) -> tuple:
        """
        Resolve a preset's eligible member binding templates, in
        stored order.

        Returns:
            An immutable tuple of the preset's registered, ACTIVE
            member binding templates, or an empty tuple if the preset
            cannot be resolved

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError:
                If the preset ID is None or blank
        """

        return self.resolve(preset_id).templates

    def _resolve_members(self, preset) -> tuple:
        resolved = []

        for template_id in preset.binding_template_ids:
            template = self._template_registry.find(template_id)

            if template is None:
                continue

            if (
                self._activation_service.state(template_id)
                != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE
            ):
                continue

            resolved.append(template)

        return tuple(resolved)

    def _validate_preset_id(self, preset_id: str) -> None:
        if preset_id is None or not preset_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError(
                "Cannot resolve a binding preset with an empty or blank preset ID."
            )

    def _validate_preset_membership(self, preset) -> None:
        if not isinstance(
            preset,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError(
                "Cannot resolve a binding preset: preset membership is corrupted."
            )

        try:
            binding_template_ids = tuple(preset.binding_template_ids)
        except TypeError as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError(
                "Cannot resolve a binding preset: preset membership is corrupted."
            ) from error

        if any(
            template_id is None or not isinstance(template_id, str) or not template_id.strip()
            for template_id in binding_template_ids
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetResolverError(
                "Cannot resolve a binding preset: preset membership is corrupted."
            )
