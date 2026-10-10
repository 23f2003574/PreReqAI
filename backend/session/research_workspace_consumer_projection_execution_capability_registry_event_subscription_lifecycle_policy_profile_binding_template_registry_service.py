from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_registry_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_registry_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistrySnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService:
    """
    Maintains a centralised registry of consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding templates, addressed by template identifier, for fast
    lookup, replacement, and snapshot generation.

    The service's responsibility is template registration,
    replacement, removal, lookup, containment checking, listing, and
    snapshot generation, not template instantiation, binding
    creation, profile validation, policy evaluation, persistence,
    logging, or event publication. It does NOT instantiate templates,
    create bindings, validate profiles, evaluate policies, persist
    the registry, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two registered templates may share a
      template ID
    - Order-preserving: Templates are listed in the order they were
      first registered
    - Immutable registry: The underlying registry value object is
      replaced atomically on every mutation rather than mutated in
      place
    """

    def __init__(self):
        self._registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistry(
            templates=MappingProxyType({})
        )

        self._lock = RLock()

    def register(self, template) -> None:
        """
        Register a binding template.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError:
                If the template is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
                has an empty or blank template ID, or its template ID
                is already registered
        """

        self._validate_template(template)

        with self._lock:
            if template.template_id in self._registry.templates:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError(
                    f"Cannot register a binding template: template ID {template.template_id!r} is already registered."
                )

            updated = dict(self._registry.templates)
            updated[template.template_id] = template

            self._replace_templates(updated)

    def replace(self, template) -> None:
        """
        Replace an already-registered binding template.

        The replaced template keeps its original position in
        registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError:
                If the template is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
                has an empty or blank template ID, or no template is
                registered under its template ID
        """

        self._validate_template(template)

        with self._lock:
            if template.template_id not in self._registry.templates:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError(
                    f"Cannot replace a binding template: no template is registered under template ID {template.template_id!r}."
                )

            updated = dict(self._registry.templates)
            updated[template.template_id] = template

            self._replace_templates(updated)

    def remove(self, template_id) -> None:
        """
        Remove the template registered under a template ID.

        Unlike a plain deletion, removing a template ID that was
        never registered is rejected rather than treated as a no-op.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError:
                If the template ID is None or blank, or no template
                is registered under it
        """

        self._validate_template_id(template_id)

        with self._lock:
            if template_id not in self._registry.templates:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError(
                    f"Cannot remove a binding template: no template is registered under template ID {template_id!r}."
                )

            updated = dict(self._registry.templates)
            del updated[template_id]

            self._replace_templates(updated)

    def find(self, template_id):
        """
        Find the template registered under a template ID.

        Returns:
            The matching template, or None if no template is
            registered under it
        """

        with self._lock:
            return self._registry.templates.get(template_id)

    def contains(self, template_id) -> bool:
        """
        Check whether a template is registered under a template ID.
        """

        with self._lock:
            return template_id in self._registry.templates

    def list(self) -> tuple:
        """
        List every registered template.

        Returns:
            An immutable tuple of every registered template,
            preserving registration order
        """

        with self._lock:
            return tuple(self._registry.templates.values())

    def snapshot(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistrySnapshot:
        """
        Take a snapshot of the registry's current state.

        Returns:
            An immutable snapshot carrying the current template count
            and the number of distinct binding identifiers referenced
            among the registered templates' members
        """

        with self._lock:
            templates = self._registry.templates

            binding_ids = set()
            for template in templates.values():
                binding_ids.update(template.binding_ids)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistrySnapshot(
                template_count=len(templates),
                binding_count=len(binding_ids),
            )

    def _replace_templates(self, templates) -> None:
        self._registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistry(
            templates=MappingProxyType(templates)
        )

    def _validate_template_id(self, template_id) -> None:
        if template_id is None or not template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError(
                "Cannot operate on a binding template with an empty or blank template ID."
            )

    def _validate_template(self, template) -> None:
        if template is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError(
                "Cannot register a None binding template."
            )

        if not isinstance(
            template,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryError(
                "Cannot register a binding template: template must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate."
            )

        self._validate_template_id(template.template_id)
