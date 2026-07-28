from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_activation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_activation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService:
    """
    Controls the activation state of consumer projection execution
    capability registry event subscription lifecycle policy profile
    bindings, so a binding can be enabled, disabled, or scheduled for
    future activation without deleting its configuration.

    The service's responsibility is activation state tracking, not
    binding creation, profile or capability validation, or
    resolution. It does NOT create bindings, validate profiles or
    capabilities, mutate the binding registry, persist state
    externally, log, or publish events. Only a binding whose state()
    is ACTIVE is eligible to participate in resolution.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Bidirectional: A binding may freely move between ACTIVE and
      INACTIVE; activation is a toggle, not a one-way pipeline
    - Idempotent: Re-activating an already-active binding, or
      re-deactivating an already-inactive one, changes nothing
    - Self-materializing: A SCHEDULED binding is recognized as ACTIVE
      as soon as its activation time is reached, without requiring a
      background process
    """

    def __init__(self, binding_registry, clock):
        """
        Args:
            binding_registry: The registry used to verify a binding
                exists. Any object exposing `find(binding_id)` is
                accepted
            clock: The clock used to timestamp activations and check
                scheduled activation times. Any object exposing
                `now()` is accepted
        """

        if binding_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError(
                "Cannot initialize activation service with a None binding registry."
            )

        if clock is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError(
                "Cannot initialize activation service with a None clock."
            )

        self._binding_registry = binding_registry
        self._clock = clock
        self._results = {}
        self._lock = RLock()

    def activate(
        self,
        binding_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationResult:
        """
        Activate a binding immediately.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError:
                If the binding ID is None or blank, or no binding is
                registered under it
        """

        self._resolve_binding(binding_id)

        with self._lock:
            previous = self._effective_state(binding_id)

            activated_at = (
                self._results[binding_id].activated_at
                if previous == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE
                else self._clock.now()
            )

            result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationResult(
                binding_id=binding_id,
                previous_state=previous,
                current_state=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE,
                activated_at=activated_at,
            )

            self._results[binding_id] = result

            return result

    def deactivate(
        self,
        binding_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationResult:
        """
        Deactivate a binding.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError:
                If the binding ID is None or blank, or no binding is
                registered under it
        """

        self._resolve_binding(binding_id)

        with self._lock:
            previous = self._effective_state(binding_id)

            result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationResult(
                binding_id=binding_id,
                previous_state=previous,
                current_state=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.INACTIVE,
                activated_at=None,
            )

            self._results[binding_id] = result

            return result

    def schedule(
        self,
        binding_id: str,
        activation_time,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationResult:
        """
        Schedule a binding to activate at a future time.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError:
                If the binding ID is None or blank, no binding is
                registered under it, activation_time is None or not
                strictly in the future, or the binding is currently
                ACTIVE
        """

        self._resolve_binding(binding_id)

        if activation_time is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError(
                "Cannot schedule a binding with a None activation time."
            )

        with self._lock:
            now = self._clock.now()

            if activation_time <= now:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError(
                    f"Cannot schedule a binding with an activation time in the past: {activation_time!r}."
                )

            previous = self._effective_state(binding_id)

            if previous == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError(
                    f"Cannot schedule binding ID {binding_id!r}: it is already active."
                )

            result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationResult(
                binding_id=binding_id,
                previous_state=previous,
                current_state=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.SCHEDULED,
                activated_at=activation_time,
            )

            self._results[binding_id] = result

            return result

    def state(
        self,
        binding_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState:
        """
        Look up a binding's current activation state.

        A SCHEDULED binding whose activation time has been reached is
        recognized and materialized as ACTIVE.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError:
                If the binding ID is None or blank, or no binding is
                registered under it
        """

        self._resolve_binding(binding_id)

        with self._lock:
            return self._effective_state(binding_id)

    def _effective_state(
        self,
        binding_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState:
        stored = self._results.get(binding_id)

        if stored is None:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.INACTIVE

        if (
            stored.current_state == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.SCHEDULED
            and self._clock.now() >= stored.activated_at
        ):
            materialized = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationResult(
                binding_id=binding_id,
                previous_state=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.SCHEDULED,
                current_state=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE,
                activated_at=stored.activated_at,
            )

            self._results[binding_id] = materialized

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE

        return stored.current_state

    def _resolve_binding(self, binding_id: str) -> None:
        if binding_id is None or not binding_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError(
                "Cannot operate with an empty or blank binding ID."
            )

        if self._binding_registry.find(binding_id) is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationError(
                f"Cannot operate: no binding is registered under binding ID {binding_id!r}."
            )
