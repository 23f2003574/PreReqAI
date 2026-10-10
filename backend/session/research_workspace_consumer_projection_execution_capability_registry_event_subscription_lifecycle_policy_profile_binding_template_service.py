from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_collection import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_collection import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCollection,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateService:
    """
    Maintains a centralised registry of reusable consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding templates, so that standardized binding
    configurations can be instantiated instead of repeatedly created
    from scratch.

    The service's responsibility is template registration,
    replacement, removal, lookup, listing, and instantiation, not
    binding creation, profile validation, policy evaluation,
    persistence, logging, or event publication. It does NOT create
    the underlying bindings, validate profiles, evaluate policies,
    persist templates, log, or publish events. Every mutation
    replaces the registry atomically; no registered template is ever
    mutated in place.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two registered templates may share a
      template ID
    - Order-preserving: Templates are listed in the order they were
      first registered, and a template's binding order is preserved
      through registration and instantiation
    - Copy-independent: Every instantiation produces brand-new
      binding records; no instantiated binding is shared between
      instantiations or with the bindings the template was built from
    """

    def __init__(self, binding_service):
        """
        Args:
            binding_service: The binding service used to verify a
                binding exists before it is referenced by a template,
                and to look up the binding a template member refers
                to when the template is instantiated. Any object
                exposing `contains(binding_id)` and `find(binding_id)`
                is accepted
        """

        if binding_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                "Cannot initialize binding template service with a None binding service."
            )

        self._binding_service = binding_service
        self._templates = MappingProxyType({})
        self._template_order = []
        self._sequence = 0
        self._lock = RLock()

    def register(
        self,
        template: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate:
        """
        Register a binding template.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError:
                If the template is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
                its template ID is already registered, or any of its
                member bindings is unknown
        """

        self._validate_template(template)

        with self._lock:
            if template.template_id in self._templates:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                    f"Cannot register a binding template: template ID {template.template_id!r} is already registered."
                )

            self._validate_members(template.binding_ids)

            updated = dict(self._templates)
            updated[template.template_id] = template
            self._templates = MappingProxyType(updated)
            self._template_order.append(template.template_id)

            return template

    def replace(
        self,
        template: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate:
        """
        Replace an already-registered binding template.

        The replaced template keeps its original position in
        registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError:
                If the template is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
                no template is registered under its template ID, or
                any of its member bindings is unknown
        """

        self._validate_template(template)

        with self._lock:
            if template.template_id not in self._templates:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                    f"Cannot replace a binding template: no template is registered under template ID {template.template_id!r}."
                )

            self._validate_members(template.binding_ids)

            updated = dict(self._templates)
            updated[template.template_id] = template
            self._templates = MappingProxyType(updated)

            return template

    def remove(
        self,
        template_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate:
        """
        Remove the template registered under a template ID.

        Unlike a plain deletion, removing a template ID that was
        never registered is rejected rather than treated as a no-op.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError:
                If the template ID is None or blank, or no template
                is registered under it
        """

        self._validate_template_id(template_id)

        with self._lock:
            if template_id not in self._templates:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                    f"Cannot remove a binding template: no template is registered under template ID {template_id!r}."
                )

            updated = dict(self._templates)
            template = updated.pop(template_id)
            self._templates = MappingProxyType(updated)
            self._template_order.remove(template_id)

            return template

    def find(self, template_id: str):
        """
        Find the template registered under a template ID.

        Returns:
            The matching template, or None if no template is
            registered under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError:
                If the template ID is None or blank
        """

        self._validate_template_id(template_id)

        with self._lock:
            return self._templates.get(template_id)

    def instantiate(
        self,
        template_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection:
        """
        Instantiate a registered binding template, producing a fresh,
        independent binding copy for every binding the template is
        built from.

        The instantiated bindings are brand-new records: each one
        carries its own generated binding ID and creation timestamp,
        and none of them is shared with the bindings the template was
        built from, nor with any other instantiation of the same
        template.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError:
                If the template ID is None or blank, no template is
                registered under it, or any of its member bindings is
                no longer known
        """

        self._validate_template_id(template_id)

        with self._lock:
            template = self._templates.get(template_id)

            if template is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                    f"Cannot instantiate a binding template: no template is registered under template ID {template_id!r}."
                )

            instances = []

            for binding_id in template.binding_ids:
                source = self._binding_service.find(binding_id)

                if source is None:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                        f"Cannot instantiate a binding template: no binding is registered under binding ID {binding_id!r}."
                    )

                self._sequence += 1

                instances.append(
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
                        binding_id=self._generate_instance_binding_id(template_id, source.binding_id, self._sequence),
                        profile_id=source.profile_id,
                        capability_id=source.capability_id,
                        created_at=datetime.now(timezone.utc),
                    )
                )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingCollection(
                bindings=tuple(instances),
            )

    def list(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCollection:
        """
        List every registered template, in deterministic order.
        """

        with self._lock:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateCollection(
                templates=tuple(self._templates[template_id] for template_id in self._template_order),
            )

    def _generate_instance_binding_id(self, template_id: str, source_binding_id: str, sequence: int) -> str:
        return f"{template_id}::{source_binding_id}::{sequence}"

    def _validate_members(self, binding_ids) -> None:
        for binding_id in binding_ids:
            if not self._binding_service.contains(binding_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                    f"Cannot save a binding template: no binding is registered under binding ID {binding_id!r}."
                )

    def _validate_template_id(self, template_id) -> None:
        if template_id is None or not template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                "Cannot operate on a binding template with an empty or blank template ID."
            )

    def _validate_template(self, template) -> None:
        if template is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                "Cannot save a None binding template."
            )

        if not isinstance(
            template,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateError(
                "Cannot save a binding template: template must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate."
            )

        self._validate_template_id(template.template_id)
