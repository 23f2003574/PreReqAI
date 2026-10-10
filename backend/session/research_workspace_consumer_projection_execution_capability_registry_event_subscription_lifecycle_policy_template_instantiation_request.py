from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest:
    """
    Immutable request to instantiate a new consumer projection
    execution capability registry event subscription lifecycle
    policy from a template.

    The request is a value object only. It performs no resolution,
    no validation, and no instantiation. Resolution, validation, and
    instantiation are the responsibility of a template instantiation
    service.

    Attributes:
        template_id: The identifier of the template to instantiate
            from
        instance_identifier: A caller-supplied identifier for the
            instance being created, unique across all instances ever
            created by a given instantiation service
    """

    template_id: str

    instance_identifier: str
