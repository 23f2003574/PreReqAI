from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_request_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder:
    """
    Builds an immutable request supplied to a lifecycle policy
    evaluator, encapsulating a lifecycle policy and a proposed
    lifecycle transition.

    The builder's responsibility is validation and capture of the
    policy and transition, not evaluation. It does NOT evaluate the
    policy, validate the transition, execute lifecycle transitions,
    mutate the policy, mutate the transition, persist requests, log,
    or compute metrics.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same policy and transition always produce the
      same request
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        policy,

        transition,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequest:
        """
        Build an evaluation request from a lifecycle policy and a
        proposed lifecycle transition.

        Args:
            policy: The lifecycle policy to evaluate against
            transition: The proposed lifecycle transition being
                evaluated

        Returns:
            An immutable policy evaluation request

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestError:
                If the policy or transition is None
        """

        if policy is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestError(
                    "Cannot build an evaluation request with a None policy."
                )
            )

        if transition is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestError(
                    "Cannot build an evaluation request with a None transition."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequest(
                policy=policy,

                transition=transition,
            )
        )
