from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_resolution_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_resolver_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolver:
    """
    Resolves the effective consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    template, and its eligible member bindings, for a template
    identifier, providing a single lookup interface for downstream
    instantiation and deployment components.

    The resolver's responsibility is centralized, deterministic
    resolution of the effective template and its members for a given
    template ID, not template creation, replacement, removal,
    validation, or persistence. It does NOT create templates, mutate
    a registry, validate templates, persist results, log, or publish
    events. A resolver works against any object exposing a
    `find(template_id)` lookup, such as a binding template registry
    service, together with a binding registry exposing
    `find(binding_id)` and an activation service exposing
    `state(binding_id)`. Only a binding that is both registered and
    ACTIVE is included among a template's resolved members; missing
    and inactive members are silently skipped, and members are
    returned in the order they are stored on the template.

    The resolver is:
    - Stateless: No mutable instance state; the registries and
      default template it was constructed with are treated as
      read-only
    - Deterministic: Same template ID and registry state always
      produce the same outcome
    - Side-effect free: Never mutates the template registry, the
      binding registry, or the activation service it resolves
      against
    """

    def __init__(
        self,
        template_registry,
        binding_registry,
        activation_service,
        default_template=None,
    ):
        """
        Args:
            template_registry: The primary lookup source to resolve
                against. Any object exposing a `find(template_id)`
                lookup is accepted
            binding_registry: The registry used to look up a
                template's member bindings. Any object exposing a
                `find(binding_id)` lookup is accepted
            activation_service: The service used to check whether a
                member binding is eligible to participate in
                resolution. Any object exposing `state(binding_id)` is
                accepted
            default_template: An optional template to fall back to
                when the registry has no template for the template ID

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError:
                If the template registry, binding registry, or
                activation service is None
        """

        if template_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError(
                "Cannot resolve binding templates against a None template registry."
            )

        if binding_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError(
                "Cannot resolve binding templates against a None binding registry."
            )

        if activation_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError(
                "Cannot resolve binding templates against a None activation service."
            )

        self._template_registry = template_registry
        self._binding_registry = binding_registry
        self._activation_service = activation_service
        self._default_template = default_template

    def resolve(
        self,
        template_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResult:
        """
        Resolve the effective binding template, and its eligible
        member bindings, for a template ID.

        The template registry is consulted first. If it has no
        template for the template ID and a default template was
        configured, the default template is used instead.

        Returns:
            An immutable resolution result. If no template is found
            in any configured source, resolved is False, template is
            None, bindings is empty, and source is None

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError:
                If the template ID is None or blank, or the resolved
                template's membership is corrupted
        """

        self._validate_template_id(template_id)

        template = self._template_registry.find(template_id)
        source = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource.REGISTRY

        if template is None:
            template = self._default_template
            source = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionSource.DEFAULT

        if template is None:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResult(
                template=None,
                bindings=(),
                resolved=False,
                source=None,
            )

        self._validate_template_membership(template)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolutionResult(
            template=template,
            bindings=self._resolve_members(template),
            resolved=True,
            source=source,
        )

    def resolve_or_raise(
        self,
        template_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate:
        """
        Resolve the effective binding template for a template ID,
        raising if it cannot be resolved.

        Returns:
            The resolved template

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError:
                If the template ID is None or blank, or no template
                could be resolved for it
        """

        result = self.resolve(template_id)

        if not result.resolved:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError(
                f"Cannot resolve a binding template for template ID {template_id!r}: no template was found."
            )

        return result.template

    def contains(self, template_id: str) -> bool:
        """
        Check whether an effective binding template can be resolved
        for a template ID.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError:
                If the template ID is None or blank
        """

        return self.resolve(template_id).resolved

    def resolve_bindings(self, template_id: str) -> tuple:
        """
        Resolve a template's eligible member bindings, in stored
        order.

        Returns:
            An immutable tuple of the template's registered, ACTIVE
            member bindings, or an empty tuple if the template cannot
            be resolved

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError:
                If the template ID is None or blank
        """

        return self.resolve(template_id).bindings

    def _resolve_members(self, template) -> tuple:
        resolved = []

        for binding_id in template.binding_ids:
            binding = self._binding_registry.find(binding_id)

            if binding is None:
                continue

            if (
                self._activation_service.state(binding_id)
                != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE
            ):
                continue

            resolved.append(binding)

        return tuple(resolved)

    def _validate_template_id(self, template_id: str) -> None:
        if template_id is None or not template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError(
                "Cannot resolve a binding template with an empty or blank template ID."
            )

    def _validate_template_membership(self, template) -> None:
        if not isinstance(
            template,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError(
                "Cannot resolve a binding template: template membership is corrupted."
            )

        try:
            binding_ids = tuple(template.binding_ids)
        except TypeError as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError(
                "Cannot resolve a binding template: template membership is corrupted."
            ) from error

        if any(binding_id is None or not isinstance(binding_id, str) or not binding_id.strip() for binding_id in binding_ids):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateResolverError(
                "Cannot resolve a binding template: template membership is corrupted."
            )
