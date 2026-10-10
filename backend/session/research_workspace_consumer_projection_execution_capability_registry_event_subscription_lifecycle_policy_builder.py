from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder:
    """
    Builds an immutable lifecycle policy describing which lifecycle
    states are permitted for a consumer projection execution
    capability registry event subscription, and which state a
    subscription starts in.

    The builder's responsibility is validation and capture of the
    allowed states and initial state, not lifecycle management. It
    does NOT validate transitions, execute transitions, activate,
    suspend, unregister, persist, log, or publish.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same allowed states and initial state always
      produce the same policy
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        allowed_states,

        initial_state,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy:
        """
        Build a lifecycle policy from allowed states and an initial
        state.

        Args:
            allowed_states: The lifecycle states permitted under this
                policy
            initial_state: The lifecycle state a subscription starts
                in

        Returns:
            An immutable lifecycle policy

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyError:
                If the allowed states are None or empty, the initial
                state is None, the allowed states contain duplicates,
                or the initial state is not among the allowed states
        """

        if allowed_states is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyError(
                    "Cannot build a lifecycle policy with None allowed states."
                )
            )

        allowed_states = tuple(
            allowed_states
        )

        if len(
            allowed_states
        ) == 0:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyError(
                    "Cannot build a lifecycle policy with empty allowed states."
                )
            )

        if len(
            set(
                allowed_states
            )
        ) != len(
            allowed_states
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyError(
                    "Cannot build a lifecycle policy with duplicate allowed states."
                )
            )

        if initial_state is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyError(
                    "Cannot build a lifecycle policy with a None initial state."
                )
            )

        if initial_state not in allowed_states:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyError(
                    "Cannot build a lifecycle policy: initial state must be one "
                    "of the allowed states."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy(
                allowed_states=allowed_states,

                initial_state=initial_state,
            )
        )
