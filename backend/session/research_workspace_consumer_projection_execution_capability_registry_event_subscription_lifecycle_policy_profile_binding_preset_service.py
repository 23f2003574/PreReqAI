from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_collection import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCollection,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetService:
    """
    Maintains a centralised registry of reusable consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding presets, so that common binding template
    groupings can be provisioned together instead of one binding
    template at a time.

    The service's responsibility is preset registration, replacement,
    removal, lookup, listing, and instantiation, not binding template
    creation, binding creation, profile validation, policy
    evaluation, persistence, logging, or event publication. It does
    NOT create the underlying binding templates or bindings, validate
    profiles, evaluate policies, persist presets, log, or publish
    events. Every mutation replaces the registry atomically; no
    registered preset is ever mutated in place.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two registered presets may share a preset ID
    - Order-preserving: Presets are listed in the order they were
      first registered, and a preset's binding template order is
      preserved through registration and instantiation
    - Copy-independent: Every instantiation produces brand-new
      binding collections, one per member binding template; no
      instantiated binding set is shared between instantiations or
      with any other preset
    """

    def __init__(self, binding_template_service):
        """
        Args:
            binding_template_service: The binding template service
                used to verify a binding template exists before it is
                referenced by a preset, and to instantiate a preset's
                member binding templates. Any object exposing
                `find(template_id)` and `instantiate(template_id)` is
                accepted
        """

        if binding_template_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError(
                "Cannot initialize binding preset service with a None binding template service."
            )

        self._binding_template_service = binding_template_service
        self._presets = MappingProxyType({})
        self._preset_order = []
        self._lock = RLock()

    def register(
        self,
        preset: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset:
        """
        Register a binding preset.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError:
                If the preset is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
                its preset ID is already registered, or any of its
                member binding templates is unknown
        """

        self._validate_preset(preset)

        with self._lock:
            if preset.preset_id in self._presets:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError(
                    f"Cannot register a binding preset: preset ID {preset.preset_id!r} is already registered."
                )

            self._validate_members(preset.binding_template_ids)

            updated = dict(self._presets)
            updated[preset.preset_id] = preset
            self._presets = MappingProxyType(updated)
            self._preset_order.append(preset.preset_id)

            return preset

    def replace(
        self,
        preset: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset:
        """
        Replace an already-registered binding preset.

        The replaced preset keeps its original position in
        registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError:
                If the preset is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
                no preset is registered under its preset ID, or any of
                its member binding templates is unknown
        """

        self._validate_preset(preset)

        with self._lock:
            if preset.preset_id not in self._presets:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError(
                    f"Cannot replace a binding preset: no preset is registered under preset ID {preset.preset_id!r}."
                )

            self._validate_members(preset.binding_template_ids)

            updated = dict(self._presets)
            updated[preset.preset_id] = preset
            self._presets = MappingProxyType(updated)

            return preset

    def remove(
        self,
        preset_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset:
        """
        Remove the preset registered under a preset ID.

        Unlike a plain deletion, removing a preset ID that was never
        registered is rejected rather than treated as a no-op.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError:
                If the preset ID is None or blank, or no preset is
                registered under it
        """

        self._validate_preset_id(preset_id)

        with self._lock:
            if preset_id not in self._presets:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError(
                    f"Cannot remove a binding preset: no preset is registered under preset ID {preset_id!r}."
                )

            updated = dict(self._presets)
            preset = updated.pop(preset_id)
            self._presets = MappingProxyType(updated)
            self._preset_order.remove(preset_id)

            return preset

    def find(self, preset_id: str):
        """
        Find the preset registered under a preset ID.

        Returns:
            The matching preset, or None if no preset is registered
            under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError:
                If the preset ID is None or blank
        """

        self._validate_preset_id(preset_id)

        with self._lock:
            return self._presets.get(preset_id)

    def instantiate(self, preset_id: str) -> tuple:
        """
        Instantiate a registered binding preset, producing an
        independent binding collection for every binding template the
        preset is built from.

        Each member binding template is instantiated on its own,
        through the binding template service, so every resulting
        binding collection is a fresh, independent binding set; none
        of them is shared with any other instantiation of the preset,
        nor with each other.

        Returns:
            An immutable tuple of binding collections, one per member
            binding template, in the preset's binding template order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError:
                If the preset ID is None or blank, no preset is
                registered under it, or any of its member binding
                templates can no longer be instantiated
        """

        self._validate_preset_id(preset_id)

        with self._lock:
            preset = self._presets.get(preset_id)

            if preset is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError(
                    f"Cannot instantiate a binding preset: no preset is registered under preset ID {preset_id!r}."
                )

            return tuple(
                self._binding_template_service.instantiate(template_id)
                for template_id in preset.binding_template_ids
            )

    def list(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCollection:
        """
        List every registered preset, in deterministic order.
        """

        with self._lock:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetCollection(
                presets=tuple(self._presets[preset_id] for preset_id in self._preset_order),
            )

    def _validate_members(self, binding_template_ids) -> None:
        for template_id in binding_template_ids:
            if self._binding_template_service.find(template_id) is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError(
                    f"Cannot save a binding preset: no binding template is registered under template ID {template_id!r}."
                )

    def _validate_preset_id(self, preset_id) -> None:
        if preset_id is None or not preset_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError(
                "Cannot operate on a binding preset with an empty or blank preset ID."
            )

    def _validate_preset(self, preset) -> None:
        if preset is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError(
                "Cannot save a None binding preset."
            )

        if not isinstance(
            preset,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetError(
                "Cannot save a binding preset: preset must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset."
            )

        self._validate_preset_id(preset.preset_id)
