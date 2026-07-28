from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_registry_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_registry_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistrySnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService:
    """
    Maintains a centralised registry of consumer projection execution
    capability registry event subscription lifecycle policy profile
    bindings, addressed by binding identifier, for fast lookup,
    replacement, and snapshot generation.

    The service's responsibility is binding registration, replacement,
    removal, lookup, containment checking, listing, and snapshot
    generation, not binding creation, profile validation, policy
    evaluation, persistence, logging, or event publication. It does
    NOT create bindings, validate profiles, evaluate policies, persist
    the registry, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two registered bindings may share a binding
      ID
    - Order-preserving: Bindings are listed in the order they were
      first registered
    - Immutable registry: The underlying registry value object is
      replaced atomically on every mutation rather than mutated in
      place
    """

    def __init__(self):
        self._registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistry(
            bindings=MappingProxyType({})
        )

        self._lock = RLock()

    def register(self, binding) -> None:
        """
        Register a profile binding.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError:
                If the binding is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
                has an empty or blank binding ID, or its binding ID is
                already registered
        """

        self._validate_binding(binding)

        with self._lock:
            if binding.binding_id in self._registry.bindings:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError(
                    f"Cannot register a binding: binding ID {binding.binding_id!r} is already registered."
                )

            updated = dict(self._registry.bindings)
            updated[binding.binding_id] = binding

            self._replace_bindings(updated)

    def replace(self, binding) -> None:
        """
        Replace an already-registered profile binding.

        The replaced binding keeps its original position in
        registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError:
                If the binding is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
                has an empty or blank binding ID, or no binding is
                registered under its binding ID
        """

        self._validate_binding(binding)

        with self._lock:
            if binding.binding_id not in self._registry.bindings:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError(
                    f"Cannot replace a binding: no binding is registered under binding ID {binding.binding_id!r}."
                )

            updated = dict(self._registry.bindings)
            updated[binding.binding_id] = binding

            self._replace_bindings(updated)

    def remove(self, binding_id) -> None:
        """
        Remove the binding registered under a binding ID.

        Unlike a plain deletion, removing a binding ID that was never
        registered is rejected rather than treated as a no-op.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError:
                If the binding ID is None or blank, or no binding is
                registered under it
        """

        self._validate_binding_id(binding_id)

        with self._lock:
            if binding_id not in self._registry.bindings:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError(
                    f"Cannot remove a binding: no binding is registered under binding ID {binding_id!r}."
                )

            updated = dict(self._registry.bindings)
            del updated[binding_id]

            self._replace_bindings(updated)

    def find(self, binding_id):
        """
        Find the binding registered under a binding ID.

        Returns:
            The matching binding, or None if no binding is registered
            under it
        """

        with self._lock:
            return self._registry.bindings.get(binding_id)

    def contains(self, binding_id) -> bool:
        """
        Check whether a binding is registered under a binding ID.
        """

        with self._lock:
            return binding_id in self._registry.bindings

    def list(self) -> tuple:
        """
        List every registered binding.

        Returns:
            An immutable tuple of every registered binding, preserving
            registration order
        """

        with self._lock:
            return tuple(self._registry.bindings.values())

    def snapshot(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistrySnapshot:
        """
        Take a snapshot of the registry's current state.

        Returns:
            An immutable snapshot carrying the current binding count
            and the number of distinct profiles and capabilities
            represented among the registered bindings
        """

        with self._lock:
            bindings = self._registry.bindings

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistrySnapshot(
                binding_count=len(bindings),
                profile_count=len({binding.profile_id for binding in bindings.values()}),
                capability_count=len({binding.capability_id for binding in bindings.values()}),
            )

    def _replace_bindings(self, bindings) -> None:
        self._registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistry(
            bindings=MappingProxyType(bindings)
        )

    def _validate_binding_id(self, binding_id) -> None:
        if binding_id is None or not binding_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError(
                "Cannot operate on a binding with an empty or blank binding ID."
            )

    def _validate_binding(self, binding) -> None:
        if binding is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError(
                "Cannot register a None binding."
            )

        if not isinstance(
            binding,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryError(
                "Cannot register a binding: binding must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding."
            )

        self._validate_binding_id(binding.binding_id)
