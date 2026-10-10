from .research_workspace_consumer_projection_execution_capability_registry_event_subscription import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder:
    """
    Builds an immutable lifecycle representation of a consumer
    projection execution capability registry event subscription's
    current state.

    The builder's responsibility is validation and capture of a
    subscription's state, not lifecycle management. It does NOT
    activate, suspend, unregister, dispatch, publish, or mutate
    subscriptions.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same subscription and state always produce the
      same lifecycle
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        subscription,

        state,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle:
        """
        Build a lifecycle capturing a subscription's current state.

        Args:
            subscription: The subscription this lifecycle describes
            state: The subscription's current lifecycle state

        Returns:
            An immutable lifecycle

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleError:
                If the subscription or state is None, or either is
                the wrong type
        """

        if subscription is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleError(
                    "Cannot build a lifecycle for a None subscription."
                )
            )

        if not isinstance(

            subscription,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleError(
                    "Cannot build a lifecycle: subscription must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscription."
                )
            )

        if state is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleError(
                    "Cannot build a lifecycle with a None state."
                )
            )

        if not isinstance(

            state,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleError(
                    "Cannot build a lifecycle: state must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle(
                subscription=subscription,

                state=state,
            )
        )
