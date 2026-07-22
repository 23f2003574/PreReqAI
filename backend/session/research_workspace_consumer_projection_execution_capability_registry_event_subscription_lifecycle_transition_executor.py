from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_transition_executor_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutorError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutor:
    """
    Applies a validated consumer projection execution capability
    registry event subscription lifecycle transition to produce a
    new immutable lifecycle.

    The executor's responsibility is to apply an already-legal
    transition, not to determine legality itself - that is
    delegated to the injected validator. It does NOT determine
    legal transitions itself, mutate the existing lifecycle,
    register subscriptions, dispatch events, publish events,
    persist state, or log.

    The executor is:
    - Stateless: No instance state beyond its injected
      collaborators
    - Deterministic: Same lifecycle and transition always produce
      the same resulting lifecycle
    - Thread-safe: No shared mutable state
    - Side-effect free: Never mutates its inputs

    Its two collaborators, the transition validator and the
    lifecycle builder, must always be supplied by the caller. The
    executor never instantiates either internally.
    """

    def __init__(

        self,

        validator,

        builder,

    ):
        self._validator = validator

        self._builder = builder

    def execute(

        self,

        lifecycle,

        transition,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle:
        """
        Apply a transition to a lifecycle, producing the resulting
        lifecycle.

        Args:
            lifecycle: The lifecycle the transition is being
                applied to
            transition: The transition describing the movement to
                apply

        Returns:
            A new immutable lifecycle whose subscription is
            transition.subscription and whose state is
            transition.to_state

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutorError:
                If the lifecycle or transition is None, either is
                the wrong type, the lifecycle's subscription differs
                from the transition's subscription, or the
                lifecycle's state differs from transition.from_state
        """

        if lifecycle is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutorError(
                    "Cannot execute a transition against a None "
                    "lifecycle."
                )
            )

        if not isinstance(

            lifecycle,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutorError(
                    "Cannot execute a transition: lifecycle must be "
                    "a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycle."
                )
            )

        if transition is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutorError(
                    "Cannot execute a None transition."
                )
            )

        if not isinstance(

            transition,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutorError(
                    "Cannot execute a transition: transition must "
                    "be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransition."
                )
            )

        if lifecycle.subscription != transition.subscription:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutorError(
                    "Cannot execute a transition: lifecycle "
                    "subscription does not match transition "
                    "subscription."
                )
            )

        if lifecycle.state != transition.from_state:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutorError(
                    "Cannot execute a transition: lifecycle state "
                    f"({lifecycle.state!r}) does not match "
                    f"transition.from_state ({transition.from_state!r})."
                )
            )

        self._validator.validate(transition)

        return self._builder.build(

            transition.subscription,

            transition.to_state,
        )
