from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_parameter import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameter,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameterSet:
    """
    Immutable, ordered collection of the configurable parameters a
    consumer projection execution capability registry event
    subscription lifecycle policy template exposes.

    The parameter set is a value object only. It performs no
    validation, no defaulting, and no application. Validation,
    defaulting, and application are the responsibility of a
    parameterization service.

    Attributes:
        parameters: An immutable, order-preserving tuple of every
            parameter in the set
    """

    parameters: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameter,
        ...,
    ]
