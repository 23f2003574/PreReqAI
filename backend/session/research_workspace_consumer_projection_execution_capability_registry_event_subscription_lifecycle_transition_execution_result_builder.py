from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_execution_result_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder:
    """
    Builds an immutable record of one completed consumer projection
    execution capability registry event subscription lifecycle
    transition.

    The builder's responsibility is validation and capture of a
    completed transition's before/after lifecycles, not execution.
    It does NOT execute transitions, validate transition legality,
    mutate lifecycle objects, persist results, publish events, log,
    or compute metrics.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same result
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        previous_lifecycle,

        transition,

        resulting_lifecycle,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResult:
        """
        Build a result capturing a completed lifecycle transition.

        Args:
            previous_lifecycle: The lifecycle before the transition
                was applied
            transition: The transition that was executed
            resulting_lifecycle: The lifecycle after the transition
                was applied

        Returns:
            An immutable execution result

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError:
                If any argument is None, is the wrong type, the
                lifecycles' subscriptions differ from the
                transition's subscription, previous_lifecycle.state
                differs from transition.from_state, or
                resulting_lifecycle.state differs from
                transition.to_state
        """

        if previous_lifecycle is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError(
                    "Cannot build a result for a None "
                    "previous_lifecycle."
                )
            )

        if not isinstance(

            previous_lifecycle,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError(
                    "Cannot build a result: previous_lifecycle must "
                    "be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle."
                )
            )

        if transition is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError(
                    "Cannot build a result for a None transition."
                )
            )

        if not isinstance(

            transition,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError(
                    "Cannot build a result: transition must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition."
                )
            )

        if resulting_lifecycle is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError(
                    "Cannot build a result for a None "
                    "resulting_lifecycle."
                )
            )

        if not isinstance(

            resulting_lifecycle,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError(
                    "Cannot build a result: resulting_lifecycle "
                    "must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle."
                )
            )

        if previous_lifecycle.subscription != transition.subscription:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError(
                    "Cannot build a result: previous_lifecycle "
                    "subscription does not match transition "
                    "subscription."
                )
            )

        if resulting_lifecycle.subscription != transition.subscription:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError(
                    "Cannot build a result: resulting_lifecycle "
                    "subscription does not match transition "
                    "subscription."
                )
            )

        if previous_lifecycle.state != transition.from_state:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError(
                    "Cannot build a result: previous_lifecycle "
                    f"state ({previous_lifecycle.state!r}) does not "
                    f"match transition.from_state "
                    f"({transition.from_state!r})."
                )
            )

        if resulting_lifecycle.state != transition.to_state:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultError(
                    "Cannot build a result: resulting_lifecycle "
                    f"state ({resulting_lifecycle.state!r}) does "
                    f"not match transition.to_state "
                    f"({transition.to_state!r})."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResult(
                previous_lifecycle=previous_lifecycle,

                transition=transition,

                resulting_lifecycle=resulting_lifecycle,
            )
        )
