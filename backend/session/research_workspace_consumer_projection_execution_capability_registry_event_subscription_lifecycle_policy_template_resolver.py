from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_resolution_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionSource,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolver:
    """
    Resolves a consumer projection execution capability registry
    event subscription lifecycle policy template by identifier
    against a registry, with optional fallback to a default
    template.

    The resolver's responsibility is centralized resolution, not
    registration, replacement, unregistration, validation, or
    versioning. It does NOT register templates, mutate a registry,
    validate templates, publish versions, persist results, log, or
    publish events. A resolver works against any object exposing a
    `find(template_id)` lookup, such as a template registry service
    or template service.

    The resolver is:
    - Stateless: No instance state
    - Deterministic: Same template ID, registry state, and default
      template ID always produce the same outcome
    - Side-effect free: Never mutates the registry it resolves
      against
    """

    def resolve(

        self,

        template_id,

        registry,

        default_template_id=None,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionResult:
        """
        Resolve a template by identifier, falling back to a default
        template identifier if a direct match is not found.

        Args:
            template_id: The template ID to resolve directly
            registry: The registry to resolve against. Any object
                exposing a `find(template_id)` lookup is accepted
            default_template_id: The template ID to fall back to if
                no direct match is found, or None to disable
                fallback

        Returns:
            An immutable resolution result. If no direct match and
            no default template ID are available,
            resolution_successful is False, resolved_template is
            None, and resolution_source is None

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError:
                If the registry is None, the template ID is blank,
                the default template ID is provided but blank, or
                the default template ID is provided but not found in
                the registry
        """

        self._validate_registry(
            registry
        )

        self._validate_identifier(
            template_id,

            "template ID",
        )

        direct_match = registry.find(
            template_id
        )

        if direct_match is not None:

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionResult(
                    resolved_template=direct_match,

                    resolution_successful=True,

                    resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionSource.DIRECT_MATCH,
                )
            )

        if default_template_id is None:

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionResult(
                    resolved_template=None,

                    resolution_successful=False,

                    resolution_source=None,
                )
            )

        self._validate_identifier(
            default_template_id,

            "default template ID",
        )

        default_template = registry.find(
            default_template_id
        )

        if default_template is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError(
                    "Cannot resolve a template: default template ID "
                    f"{default_template_id!r} was not found in the "
                    "registry."
                )
            )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionResult(
                resolved_template=default_template,

                resolution_successful=True,

                resolution_source=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolutionSource.DEFAULT_TEMPLATE,
            )
        )

    def resolve_or_raise(

        self,

        template_id,

        registry,

    ):
        """
        Resolve a template by identifier, raising if it cannot be
        resolved.

        Args:
            template_id: The template ID to resolve
            registry: The registry to resolve against

        Returns:
            The resolved template

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError:
                If the registry is None, the template ID is blank,
                or no template is found under the template ID
        """

        result = self.resolve(

            template_id,

            registry,
        )

        if not result.resolution_successful:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError(
                    f"Cannot resolve template ID {template_id!r}: no "
                    "matching template was found."
                )
            )

        return result.resolved_template

    def can_resolve(

        self,

        template_id,

        registry,

    ) -> bool:
        """
        Check whether a template ID can be resolved directly.

        Args:
            template_id: The template ID to check
            registry: The registry to resolve against

        Returns:
            True if a template is registered under the template ID,
            False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError:
                If the registry is None or the template ID is blank
        """

        self._validate_registry(
            registry
        )

        self._validate_identifier(
            template_id,

            "template ID",
        )

        return registry.find(
            template_id
        ) is not None

    def _validate_registry(

        self,

        registry,

    ) -> None:

        if registry is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError(
                    "Cannot resolve a template against a None registry."
                )
            )

    def _validate_identifier(

        self,

        identifier,

        label,

    ) -> None:

        if (

            identifier is None

            or not identifier.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateResolverError(
                    f"Cannot resolve a template with an empty or blank {label}."
                )
            )
