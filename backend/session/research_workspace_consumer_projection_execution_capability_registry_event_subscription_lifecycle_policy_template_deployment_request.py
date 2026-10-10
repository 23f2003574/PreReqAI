from dataclasses import (
    dataclass,
)

from typing import Any


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest:
    """
    Immutable request to deploy a consumer projection execution
    capability registry event subscription lifecycle policy
    template into a runtime registry.

    The request is a value object only. It performs no resolution,
    no validation, and no deployment. Resolution, validation, and
    deployment are the responsibility of a deployment service.

    Attributes:
        template_id: The identifier of the template to deploy. The
            template must already be present in target_registry
        target_registry: The registry the deployed policy is
            published into. Any object exposing
            `find(template_id)`, `contains(template_id)`,
            `register(template)`, and `replace(template)` is
            accepted, such as a template registry service
    """

    template_id: str

    target_registry: Any
