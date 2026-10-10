from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_deployment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_deployment_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_deployment_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_validator import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator,
)

_REQUIRED_REGISTRY_METHODS = (
    "find",

    "contains",

    "register",

    "replace",
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService:
    """
    Deploys an approved consumer projection execution capability
    registry event subscription lifecycle policy template into a
    runtime registry: resolve the template, validate it, instantiate
    a fresh policy instance, and publish it back into the target
    registry.

    The service's responsibility is orchestrating deployment, not
    template registration, resolution strategy, or the target
    registry's own storage. It does NOT register templates
    independently of a deployment, mutate a template, persist
    results outside the target registry, log, or publish events.

    The service is:
    - Thread-safe: Deployment conflict bookkeeping is guarded by an
      internal lock
    - Conflict-aware: deploy() rejects redeploying a template ID
      that has already been deployed; deploy_or_replace() does not
    - Side-effect free on the template: Never mutates the resolved
      template; the target registry's other entries are left
      untouched
    """

    def __init__(self):

        self._validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator()

        self._deployed_template_ids = set()

        self._lock = RLock()

    def deploy(

        self,

        request,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentResult:
        """
        Deploy a template into its target registry.

        Args:
            request: The deployment request naming the template and
                target registry

        Returns:
            An immutable deployment result carrying the newly
            published lifecycle policy instance

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError:
                If the request is None, has a blank template ID or
                an invalid target registry, no template is found
                under the template ID, the resolved template fails
                validation, or the template ID has already been
                deployed
        """

        return self._deploy(

            request,

            allow_redeploy=False,
        )

    def deploy_or_replace(

        self,

        request,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentResult:
        """
        Deploy a template into its target registry, replacing any
        deployment already made for the same template ID rather than
        rejecting it as a conflict.

        Args:
            request: The deployment request naming the template and
                target registry

        Returns:
            An immutable deployment result carrying the newly
            published lifecycle policy instance

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError:
                If the request is None, has a blank template ID or
                an invalid target registry, no template is found
                under the template ID, or the resolved template
                fails validation
        """

        return self._deploy(

            request,

            allow_redeploy=True,
        )

    def can_deploy(

        self,

        request,

    ) -> bool:
        """
        Check whether deploy() would currently succeed for a
        request.

        Args:
            request: The deployment request naming the template and
                target registry

        Returns:
            True if the template exists, is valid, and has not
            already been deployed, False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError:
                If the request is None, has a blank template ID, or
                has an invalid target registry
        """

        self._validate_request(
            request
        )

        with self._lock:

            if request.template_id in self._deployed_template_ids:

                return False

            template = request.target_registry.find(
                request.template_id
            )

            if template is None:

                return False

            return self._validator.validate(
                template
            ).valid

    def _deploy(

        self,

        request,

        allow_redeploy,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentResult:

        self._validate_request(
            request
        )

        with self._lock:

            if (

                not allow_redeploy

                and request.template_id in self._deployed_template_ids
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError(
                        "Cannot deploy: template ID "
                        f"{request.template_id!r} has already been "
                        "deployed."
                    )
                )

            template = request.target_registry.find(
                request.template_id
            )

            if template is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError(
                        "Cannot deploy: no template was found under "
                        f"template ID {request.template_id!r}."
                    )
                )

            validation = self._validator.validate(
                template
            )

            if not validation.valid:

                violation_codes = ", ".join(

                    violation.code

                    for violation

                    in validation.violations
                )

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError(
                        f"Cannot deploy template {request.template_id!r}: "
                        f"failed validation: {violation_codes}."
                    )
                )

            source = template.lifecycle_policy

            deployed_policy = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy(
                    allowed_states=tuple(
                        source.allowed_states
                    ),

                    initial_state=source.initial_state,
                )
            )

            deployed_template = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
                    template_id=template.template_id,

                    template_name=template.template_name,

                    description=template.description,

                    lifecycle_policy=deployed_policy,
                )
            )

            request.target_registry.replace(
                deployed_template
            )

            self._deployed_template_ids.add(
                request.template_id
            )

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentResult(
                    deployed_policy=deployed_policy,

                    template_id=request.template_id,

                    deployment_successful=True,

                    deployed_at=datetime.now(
                        timezone.utc
                    ),
                )
            )

    def _validate_request(

        self,

        request,

    ) -> None:

        if request is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError(
                    "Cannot deploy from a None request."
                )
            )

        if not isinstance(

            request,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError(
                    "Cannot deploy: request must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest."
                )
            )

        if (

            request.template_id is None

            or not request.template_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError(
                    "Cannot deploy with an empty or blank template ID."
                )
            )

        if request.target_registry is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError(
                    "Cannot deploy to a None target registry."
                )
            )

        for method_name in _REQUIRED_REGISTRY_METHODS:

            if not callable(

                getattr(
                    request.target_registry,

                    method_name,

                    None,
                )
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError(
                        "Cannot deploy: target registry is invalid, it must "
                        f"expose a callable {method_name!r}."
                    )
                )
