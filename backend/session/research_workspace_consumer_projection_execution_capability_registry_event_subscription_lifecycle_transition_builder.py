from .research_workspace_consumer_projection_execution_capability_registry_event_subscription import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder:
    """
    Builds an immutable transition describing a consumer projection
    execution capability registry event subscription's movement
    between two lifecycle states.

    The builder's responsibility is validation and capture of a
    proposed transition, not execution. It does NOT execute state
    changes, validate legal transition paths, activate, suspend,
    unregister, publish, or persist state.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same subscription and states always produce
      the same transition
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        subscription,

        from_state,

        to_state,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition:
        """
        Build a transition describing movement between two
        lifecycle states.

        Args:
            subscription: The subscription this transition describes
            from_state: The lifecycle state being moved from
            to_state: The lifecycle state being moved to

        Returns:
            An immutable lifecycle transition

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError:
                If the subscription, from_state, or to_state is
                None, either state is the wrong type, or from_state
                equals to_state
        """

        if subscription is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError(
                    "Cannot build a transition for a None subscription."
                )
            )

        if not isinstance(

            subscription,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError(
                    "Cannot build a transition: subscription must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription."
                )
            )

        if from_state is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError(
                    "Cannot build a transition with a None from_state."
                )
            )

        if not isinstance(

            from_state,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError(
                    "Cannot build a transition: from_state must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState."
                )
            )

        if to_state is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError(
                    "Cannot build a transition with a None to_state."
                )
            )

        if not isinstance(

            to_state,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError(
                    "Cannot build a transition: to_state must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState."
                )
            )

        if from_state == to_state:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionError(
                    "Cannot build a transition: from_state and to_state "
                    f"must differ (both were {from_state!r})."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition(
                subscription=subscription,

                from_state=from_state,

                to_state=to_state,
            )
        )
