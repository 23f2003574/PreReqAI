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

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_instantiation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_instantiation_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_instantiation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_resolver import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_validator import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationService:
    """
    Runs the reusable pipeline that resolves, validates, and
    instantiates a consumer projection execution capability registry
    event subscription lifecycle policy from a template: resolve the
    template, validate it, clone its lifecycle policy, and assign
    the request's instance identifier.

    The service's responsibility is orchestrating instantiation, not
    template registration, replacement, versioning, or resolution
    strategy. It does NOT register templates, mutate a registry,
    mutate a template, publish versions, persist results, log, or
    publish events.

    The service is:
    - Thread-safe: Instance identifier bookkeeping is guarded by an
      internal lock
    - Duplicate-free: No two instantiations may share an instance
      identifier
    - Side-effect free on its inputs: Never mutates the template or
      registry it instantiates from
    """

    def __init__(self):

        self._resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver()

        self._validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator()

        self._used_instance_identifiers = set()

        self._lock = RLock()

    def instantiate(

        self,

        request,

        registry,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationResult:
        """
        Instantiate a new lifecycle policy from a template.

        Args:
            request: The instantiation request describing which
                template to instantiate from and the identifier to
                assign to the new instance
            registry: The registry to resolve the template against

        Returns:
            An immutable instantiation result carrying a newly
            created, independent lifecycle policy

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError:
                If the request or registry is None, the request has
                a blank template ID or instance identifier, no
                template is found under the template ID, the
                resolved template fails validation, or the request's
                instance identifier has already been used
        """

        self._validate_request(
            request
        )

        if registry is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError(
                    "Cannot instantiate a lifecycle policy against a None "
                    "registry."
                )
            )

        with self._lock:

            if request.instance_identifier in self._used_instance_identifiers:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError(
                        "Cannot instantiate a lifecycle policy: instance "
                        f"identifier {request.instance_identifier!r} has "
                        "already been used."
                    )
                )

            try:

                template = self._resolver.resolve_or_raise(

                    request.template_id,

                    registry,
                )

            except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError as error:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError(
                        "Cannot instantiate a lifecycle policy: no template "
                        f"was found under template ID {request.template_id!r}."
                    )
                ) from error

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
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError(
                        "Cannot instantiate a lifecycle policy: template "
                        f"{request.template_id!r} failed validation: "
                        f"{violation_codes}."
                    )
                )

            source = template.lifecycle_policy

            cloned_policy = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy(
                    allowed_states=tuple(
                        source.allowed_states
                    ),

                    initial_state=source.initial_state,
                )
            )

            self._used_instance_identifiers.add(
                request.instance_identifier
            )

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationResult(
                    lifecycle_policy=cloned_policy,

                    template_id=template.template_id,

                    instantiated_at=datetime.now(
                        timezone.utc
                    ),
                )
            )

    def instantiate_or_raise(

        self,

        request,

        registry,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationResult:
        """
        Instantiate a new lifecycle policy from a template.

        This is equivalent to instantiate(): every failure mode
        already raises, since an instantiation result carries no
        failure state of its own. It is provided so callers can
        express intent explicitly when instantiation must succeed.

        Args:
            request: The instantiation request describing which
                template to instantiate from and the identifier to
                assign to the new instance
            registry: The registry to resolve the template against

        Returns:
            An immutable instantiation result carrying a newly
            created, independent lifecycle policy

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError:
                Under the same conditions as instantiate()
        """

        return self.instantiate(

            request,

            registry,
        )

    def _validate_request(

        self,

        request,

    ) -> None:

        if request is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError(
                    "Cannot instantiate a lifecycle policy from a None "
                    "request."
                )
            )

        if not isinstance(

            request,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError(
                    "Cannot instantiate a lifecycle policy: request must be "
                    "a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationRequest."
                )
            )

        if (

            request.template_id is None

            or not request.template_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError(
                    "Cannot instantiate a lifecycle policy with an empty or "
                    "blank template ID."
                )
            )

        if (

            request.instance_identifier is None

            or not request.instance_identifier.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateInstantiationError(
                    "Cannot instantiate a lifecycle policy with an empty or "
                    "blank instance identifier."
                )
            )
