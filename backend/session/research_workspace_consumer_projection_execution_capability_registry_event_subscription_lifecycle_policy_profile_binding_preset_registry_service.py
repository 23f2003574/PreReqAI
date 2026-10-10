from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_registry_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_registry_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistrySnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService:
    """
    Maintains a centralised registry of consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding presets, addressed by preset identifier, for fast lookup,
    replacement, and snapshot generation.

    The service's responsibility is preset registration, replacement,
    removal, lookup, containment checking, listing, and snapshot
    generation, not preset instantiation, binding template creation,
    binding creation, profile validation, policy evaluation,
    persistence, logging, or event publication. It does NOT
    instantiate presets, create binding templates or bindings,
    validate profiles, evaluate policies, persist the registry, log,
    or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two registered presets may share a preset ID
    - Order-preserving: Presets are listed in the order they were
      first registered
    - Immutable registry: The underlying registry value object is
      replaced atomically on every mutation rather than mutated in
      place
    """

    def __init__(self):
        self._registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistry(
            presets=MappingProxyType({})
        )

        self._lock = RLock()

    def register(self, preset) -> None:
        """
        Register a binding preset.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError:
                If the preset is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
                has an empty or blank preset ID, or its preset ID is
                already registered
        """

        self._validate_preset(preset)

        with self._lock:
            if preset.preset_id in self._registry.presets:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError(
                    f"Cannot register a binding preset: preset ID {preset.preset_id!r} is already registered."
                )

            updated = dict(self._registry.presets)
            updated[preset.preset_id] = preset

            self._replace_presets(updated)

    def replace(self, preset) -> None:
        """
        Replace an already-registered binding preset.

        The replaced preset keeps its original position in
        registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError:
                If the preset is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
                has an empty or blank preset ID, or no preset is
                registered under its preset ID
        """

        self._validate_preset(preset)

        with self._lock:
            if preset.preset_id not in self._registry.presets:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError(
                    f"Cannot replace a binding preset: no preset is registered under preset ID {preset.preset_id!r}."
                )

            updated = dict(self._registry.presets)
            updated[preset.preset_id] = preset

            self._replace_presets(updated)

    def remove(self, preset_id) -> None:
        """
        Remove the preset registered under a preset ID.

        Unlike a plain deletion, removing a preset ID that was never
        registered is rejected rather than treated as a no-op.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError:
                If the preset ID is None or blank, or no preset is
                registered under it
        """

        self._validate_preset_id(preset_id)

        with self._lock:
            if preset_id not in self._registry.presets:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError(
                    f"Cannot remove a binding preset: no preset is registered under preset ID {preset_id!r}."
                )

            updated = dict(self._registry.presets)
            del updated[preset_id]

            self._replace_presets(updated)

    def find(self, preset_id):
        """
        Find the preset registered under a preset ID.

        Returns:
            The matching preset, or None if no preset is registered
            under it
        """

        with self._lock:
            return self._registry.presets.get(preset_id)

    def contains(self, preset_id) -> bool:
        """
        Check whether a preset is registered under a preset ID.
        """

        with self._lock:
            return preset_id in self._registry.presets

    def list(self) -> tuple:
        """
        List every registered preset.

        Returns:
            An immutable tuple of every registered preset, preserving
            registration order
        """

        with self._lock:
            return tuple(self._registry.presets.values())

    def snapshot(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistrySnapshot:
        """
        Take a snapshot of the registry's current state.

        Returns:
            An immutable snapshot carrying the current preset count
            and the number of distinct binding template identifiers
            referenced among the registered presets' members
        """

        with self._lock:
            presets = self._registry.presets

            template_ids = set()
            for preset in presets.values():
                template_ids.update(preset.binding_template_ids)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistrySnapshot(
                preset_count=len(presets),
                template_count=len(template_ids),
            )

    def _replace_presets(self, presets) -> None:
        self._registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistry(
            presets=MappingProxyType(presets)
        )

    def _validate_preset_id(self, preset_id) -> None:
        if preset_id is None or not preset_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError(
                "Cannot operate on a binding preset with an empty or blank preset ID."
            )

    def _validate_preset(self, preset) -> None:
        if preset is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError(
                "Cannot register a None binding preset."
            )

        if not isinstance(
            preset,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryError(
                "Cannot register a binding preset: preset must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset."
            )

        self._validate_preset_id(preset.preset_id)
