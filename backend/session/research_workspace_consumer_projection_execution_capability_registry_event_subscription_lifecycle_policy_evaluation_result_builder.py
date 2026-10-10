from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_result_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder:
    """
    Builds an immutable result capturing the outcome of evaluating a
    lifecycle policy against a proposed lifecycle transition.

    The builder's responsibility is validation and capture of the
    evaluation outcome, not evaluation itself. It does NOT evaluate
    policies, validate transitions, execute lifecycle transitions,
    mutate requests, persist results, publish events, log, or compute
    metrics.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same request, approval, and rejection reason
      always produce the same result
    - Side-effect free: Never mutates its inputs
    """

    def build(

        self,

        request,

        approved,

        rejection_reason=None,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResult:
        """
        Build an evaluation result from a request, an approval
        outcome, and an optional rejection reason.

        Args:
            request: The evaluation request this result is for
            approved: Whether the transition complies with the policy
            rejection_reason: The reason the transition was rejected,
                or None if approved

        Returns:
            An immutable policy evaluation result

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultError:
                If the request is None, an approved result carries a
                rejection reason, or a rejected result lacks one
        """

        if request is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultError(
                    "Cannot build an evaluation result with a None request."
                )
            )

        if approved and rejection_reason is not None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultError(
                    "Cannot build an approved evaluation result with a "
                    "rejection reason."
                )
            )

        if not approved and rejection_reason is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultError(
                    "Cannot build a rejected evaluation result without a "
                    "rejection reason."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResult(
                request=request,

                approved=approved,

                rejection_reason=rejection_reason,
            )
        )
