from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_evaluator_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluatorError,
)


_REJECTION_REASON = (
    "Lifecycle state is not permitted by policy."
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluator:
    """
    Determines whether a proposed consumer projection execution
    capability registry event subscription lifecycle transition
    satisfies a lifecycle policy.

    The evaluator's responsibility is compliance determination, not
    execution. It does NOT execute lifecycle transitions, validate
    transition legality, mutate policies, modify lifecycle state,
    persist evaluations, publish events, log, or compute metrics.

    The evaluator is:
    - Stateless: No instance state beyond its injected collaborators
    - Deterministic: Same request always produces the same result
    - Thread-safe: No shared mutable state
    - Side-effect free: Never mutates its inputs

    Its two collaborators, the policy validator and the result
    builder, must always be supplied by the caller. The evaluator
    never instantiates either internally.
    """

    def __init__(

        self,

        policy_validator,

        result_builder,

    ):
        self._policy_validator = policy_validator

        self._result_builder = result_builder

    def evaluate(

        self,

        request,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResult:
        """
        Evaluate whether a proposed lifecycle transition satisfies a
        lifecycle policy.

        Args:
            request: The evaluation request carrying the policy and
                the proposed transition

        Returns:
            An immutable evaluation result describing whether the
            transition is approved

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluatorError:
                If the request is None

        The injected policy validator may itself raise if the
        request's policy is not internally consistent.
        """

        if request is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluatorError(
                    "Cannot evaluate a None request."
                )
            )

        self._policy_validator.validate(
            request.policy
        )

        approved = (
            request.transition.from_state in request.policy.allowed_states
            and request.transition.to_state in request.policy.allowed_states
        )

        rejection_reason = (
            None
            if approved
            else _REJECTION_REASON
        )

        return self._result_builder.build(

            request,

            approved,

            rejection_reason,
        )
