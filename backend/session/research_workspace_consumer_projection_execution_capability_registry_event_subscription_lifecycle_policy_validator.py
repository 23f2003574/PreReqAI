from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_validation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidator:
    """
    Validates that a consumer projection execution capability
    registry event subscription lifecycle policy is internally
    consistent.

    The validator's responsibility is policy integrity checking, not
    execution. It does NOT validate transitions, execute lifecycle
    changes, modify policies, create policies, persist configuration,
    publish events, log, or compute metrics.

    The validator is:
    - Stateless: No instance state
    - Deterministic: Same policy always produces the same outcome
    - Thread-safe: Reads only its input
    - Side-effect free: Never mutates its input
    """

    def validate(

        self,

        policy: (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy
        ),

    ) -> None:
        """
        Validate that a lifecycle policy is internally consistent.

        Args:
            policy: The lifecycle policy to validate

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError:
                If the policy is None, its allowed states are empty
                or contain duplicates or invalid types, or its
                initial state is missing or not among the allowed
                states
        """

        if policy is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError(
                    "Cannot validate a None lifecycle policy."
                )
            )

        if not policy.allowed_states:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError(
                    "Cannot validate a lifecycle policy with empty allowed states."
                )
            )

        for state in policy.allowed_states:

            if not isinstance(

                state,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError(
                        "Cannot validate a lifecycle policy: allowed states must be "
                        "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState "
                        "values."
                    )
                )

        if policy.initial_state is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError(
                    "Cannot validate a lifecycle policy with a missing initial state."
                )
            )

        if policy.initial_state not in policy.allowed_states:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError(
                    "Cannot validate a lifecycle policy: initial state must be one "
                    "of the allowed states."
                )
            )

        if len(
            set(
                policy.allowed_states
            )
        ) != len(
            policy.allowed_states
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyValidationError(
                    "Cannot validate a lifecycle policy with duplicate allowed states."
                )
            )
