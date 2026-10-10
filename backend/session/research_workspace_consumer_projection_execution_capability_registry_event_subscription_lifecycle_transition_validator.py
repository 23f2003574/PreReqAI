from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_validation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidationError,
)


_ALLOWED_TRANSITIONS = frozenset(
    {
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        ),
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.SUSPENDED,
        ),
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.SUSPENDED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        ),
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.UNREGISTERED,
        ),
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.UNREGISTERED,
        ),
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.SUSPENDED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.UNREGISTERED,
        ),
    }
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidator:
    """
    Validates whether a consumer projection execution capability
    registry event subscription lifecycle transition is permitted.

    The validator's responsibility is legality checking, not
    execution. It does NOT execute transitions, modify lifecycle
    state, activate, suspend, unregister, publish, or persist state.

    The validator is:
    - Stateless: No instance state
    - Deterministic: Same transition always produces the same
      outcome
    - Thread-safe: Reads only immutable module-level data
    - Side-effect free: Never mutates its inputs
    """

    def validate(
        self,

        transition,

    ) -> None:
        """
        Validate that a lifecycle transition is permitted.

        Args:
            transition: The lifecycle transition to validate

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidationError:
                If the transition is None or is not among the
                permitted state pairs
        """

        if transition is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidationError(
                    "Cannot validate a None transition."
                )
            )

        if not isinstance(

            transition,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidationError(
                    "Cannot validate a transition: transition must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition."
                )
            )

        if (
            transition.from_state,
            transition.to_state,
        ) not in _ALLOWED_TRANSITIONS:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionValidationError(
                    "Cannot validate a transition: "
                    f"{transition.from_state!r} -> {transition.to_state!r} "
                    "is not a permitted lifecycle transition."
                )
            )
