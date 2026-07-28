from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_priority import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriority,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_priority_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_priority_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState,
)

_DEFAULT_PRIORITY = 0


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityService:
    """
    Supports multiple eligible consumer projection execution
    capability registry event subscription lifecycle policy profile
    bindings for the same capability by resolving a single winner
    through deterministic priority-based selection.

    The service's responsibility is priority assignment and
    selection, not binding creation, activation, or resolution. It
    does NOT create bindings, activate or deactivate bindings, mutate
    the binding registry, persist state externally, log, or publish
    events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Deterministic: Higher priority always wins; bindings that share
      a priority are ordered by binding ID, ascending, for a stable
      tie-break
    - Active-only: An inactive binding is never selected or counted
      among the evaluated bindings
    - Immutable results: Every resolution produces a new, immutable
      result
    """

    def __init__(self, binding_registry, activation_service):
        """
        Args:
            binding_registry: The registry used to resolve a binding
                ID and to find every binding for a capability. Any
                object exposing `find(binding_id)` and
                `find_by_capability(capability_id)` (returning an
                object with a `bindings` tuple) is accepted
            activation_service: The service used to check whether a
                binding is active. Any object exposing
                `state(binding_id)` is accepted
        """

        if binding_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError(
                "Cannot initialize priority service with a None binding registry."
            )

        if activation_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError(
                "Cannot initialize priority service with a None activation service."
            )

        self._binding_registry = binding_registry
        self._activation_service = activation_service
        self._priorities = {}
        self._lock = RLock()

    def set_priority(self, binding_id: str, priority: int) -> None:
        """
        Assign (or update) a binding's selection priority.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError:
                If the binding ID is None or blank, no binding is
                registered under it, or priority is None or negative
        """

        self._resolve_binding(binding_id)

        priority_record = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriority(
            binding_id=binding_id,
            priority=priority,
        )

        with self._lock:
            self._priorities[binding_id] = priority_record

    def resolve_highest_priority(
        self,
        capability_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityResult:
        """
        Resolve the single highest-priority active binding for a
        capability.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError:
                If the capability ID is None or blank
        """

        evaluated = self.ordered_bindings(capability_id)

        selected = evaluated[0] if evaluated else None

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityResult(
            selected_binding=selected,
            evaluated_bindings=evaluated,
        )

    def ordered_bindings(self, capability_id: str) -> tuple:
        """
        List every active binding for a capability, ordered from
        highest to lowest priority, with equal priorities broken by
        binding ID, ascending.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError:
                If the capability ID is None or blank
        """

        self._validate_identifier(capability_id, "capability ID")

        candidates = self._binding_registry.find_by_capability(capability_id).bindings

        active_candidates = [
            binding
            for binding in candidates
            if self._activation_service.state(binding.binding_id) == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE
        ]

        with self._lock:
            ordered = sorted(
                active_candidates,
                key=lambda binding: (-self._priority_of(binding.binding_id), binding.binding_id),
            )

        return tuple(ordered)

    def highest_priority(self, binding_id: str) -> int:
        """
        Look up a binding's currently assigned priority.

        Returns:
            The binding's priority, or 0 if none has ever been
            assigned

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError:
                If the binding ID is None or blank, or no binding is
                registered under it
        """

        self._resolve_binding(binding_id)

        with self._lock:
            return self._priority_of(binding_id)

    def _priority_of(self, binding_id: str) -> int:
        priority_record = self._priorities.get(binding_id)

        return priority_record.priority if priority_record is not None else _DEFAULT_PRIORITY

    def _resolve_binding(self, binding_id: str):
        self._validate_identifier(binding_id, "binding ID")

        binding = self._binding_registry.find(binding_id)

        if binding is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError(
                f"Cannot operate: no binding is registered under binding ID {binding_id!r}."
            )

        return binding

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPriorityError(
                f"Cannot operate with an empty or blank {label}."
            )
