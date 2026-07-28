from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_collection import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingService:
    """
    Explicitly binds consumer projection execution capability
    registry event subscription lifecycle policy profiles to
    execution capabilities, enabling reusable profile-to-capability
    mappings.

    The service's responsibility is binding lifecycle tracking, not
    profile registration, policy evaluation, or lifecycle transition
    execution. It does NOT register profiles, evaluate policies,
    execute lifecycle transitions, mutate an existing binding record,
    persist bindings externally, log, or publish events. Every bind
    produces a new, immutable binding record; no binding record is
    ever mutated.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two bindings may share the same
      (profile_id, capability_id) pair
    - Unrestricted fan-out: A profile may be bound to any number of
      capabilities, and a capability may be bound to any number of
      profiles
    - Order-preserving: Bindings are listed in the order they were
      first created
    """

    def __init__(self, profile_service):
        """
        Args:
            profile_service: The profile service used to verify a
                profile exists before it is bound. Any object
                exposing `contains(profile_id)` is accepted
        """

        if profile_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError(
                "Cannot initialize binding service with a None profile service."
            )

        self._profile_service = profile_service
        self._bindings = {}
        self._binding_order = []
        self._sequence = 0
        self._lock = RLock()

    def bind(
        self,
        profile_id: str,
        capability_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding:
        """
        Bind a profile to an execution capability.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError:
                If profile_id or capability_id is None or blank, no
                profile is registered under profile_id, or the
                (profile_id, capability_id) pair is already bound
        """

        self._validate_identifier(profile_id, "profile ID")
        self._validate_identifier(capability_id, "capability ID")

        if not self._profile_service.contains(profile_id):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError(
                f"Cannot bind: no profile is registered under profile ID {profile_id!r}."
            )

        with self._lock:
            if any(
                existing.profile_id == profile_id and existing.capability_id == capability_id
                for existing in self._bindings.values()
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError(
                    f"Cannot bind: profile ID {profile_id!r} is already bound to capability ID {capability_id!r}."
                )

            self._sequence += 1

            binding = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
                binding_id=self._generate_binding_id(profile_id, capability_id, self._sequence),
                profile_id=profile_id,
                capability_id=capability_id,
                created_at=datetime.now(timezone.utc),
            )

            self._bindings[binding.binding_id] = binding
            self._binding_order.append(binding.binding_id)

            return binding

    def unbind(
        self,
        binding_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding:
        """
        Remove a binding.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError:
                If binding_id is None or blank, or no binding is
                registered under binding_id
        """

        self._validate_identifier(binding_id, "binding ID")

        with self._lock:
            if binding_id not in self._bindings:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError(
                    f"Cannot unbind: no binding is registered under binding ID {binding_id!r}."
                )

            binding = self._bindings.pop(binding_id)
            self._binding_order.remove(binding_id)

            return binding

    def find(self, binding_id: str):
        """
        Find a binding by its binding ID.

        Returns:
            The binding registered under binding_id, or None if none
            is registered

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError:
                If binding_id is None or blank
        """

        self._validate_identifier(binding_id, "binding ID")

        with self._lock:
            return self._bindings.get(binding_id)

    def find_by_profile(
        self,
        profile_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection:
        """
        Find every binding for a profile, in deterministic order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError:
                If profile_id is None or blank
        """

        self._validate_identifier(profile_id, "profile ID")

        with self._lock:
            matching = tuple(
                self._bindings[binding_id]
                for binding_id in self._binding_order
                if self._bindings[binding_id].profile_id == profile_id
            )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection(
            bindings=matching,
        )

    def find_by_capability(
        self,
        capability_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection:
        """
        Find every binding for an execution capability, in
        deterministic order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError:
                If capability_id is None or blank
        """

        self._validate_identifier(capability_id, "capability ID")

        with self._lock:
            matching = tuple(
                self._bindings[binding_id]
                for binding_id in self._binding_order
                if self._bindings[binding_id].capability_id == capability_id
            )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection(
            bindings=matching,
        )

    def list(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection:
        """
        List every binding, in deterministic order.
        """

        with self._lock:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection(
                bindings=tuple(self._bindings[binding_id] for binding_id in self._binding_order),
            )

    def _generate_binding_id(self, profile_id: str, capability_id: str, sequence: int) -> str:
        return f"{profile_id}::{capability_id}::{sequence}"

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingError(
                f"Cannot perform binding operation with an empty or blank {label}."
            )
