from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_registry_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_registry_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistrySnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService:
    """
    Maintains a dedicated registry of consumer projection execution
    capability registry event subscription lifecycle policy
    templates, managed independently from any runtime lifecycle
    policy.

    The service's responsibility is template registration,
    replacement, unregistration, lookup, and snapshot generation,
    not template validation, versioning, policy evaluation,
    lifecycle transition execution, persistence, logging, or event
    publication. It does NOT validate templates, publish versions,
    evaluate policies, execute lifecycle transitions, persist the
    registry, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an
      internal lock
    - Duplicate-free: No two registered templates may share a
      template ID
    - Order-preserving: Templates are listed in the order they were
      first registered
    """

    def __init__(self):

        self._registry = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistry(
                templates=MappingProxyType({})
            )
        )

        self._lock = RLock()

    def register(

        self,

        template,

    ) -> None:
        """
        Register a lifecycle policy template.

        Args:
            template: The template to register

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError:
                If the template is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
                has an empty or blank template ID, or its template ID
                is already registered
        """

        self._validate_template(
            template
        )

        with self._lock:

            if template.template_id in self._registry.templates:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError(
                        "Cannot register a template: template ID "
                        f"{template.template_id!r} is already registered."
                    )
                )

            updated = dict(
                self._registry.templates
            )

            updated[template.template_id] = template

            self._replace_templates(
                updated
            )

    def replace(

        self,

        template,

    ) -> None:
        """
        Replace an already-registered lifecycle policy template.

        The replaced template keeps its original position in
        registration order.

        Args:
            template: The template to replace the existing one with

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError:
                If the template is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
                has an empty or blank template ID, or no template is
                registered under its template ID
        """

        self._validate_template(
            template
        )

        with self._lock:

            if template.template_id not in self._registry.templates:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError(
                        "Cannot replace a template: no template is "
                        f"registered under template ID {template.template_id!r}."
                    )
                )

            updated = dict(
                self._registry.templates
            )

            updated[template.template_id] = template

            self._replace_templates(
                updated
            )

    def unregister(

        self,

        template_id,

    ) -> None:
        """
        Unregister the template registered under a template ID.

        Unlike a plain removal, unregistering a template ID that
        was never registered is rejected rather than treated as a
        no-op.

        Args:
            template_id: The template ID to unregister

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError:
                If the template ID is None or blank, or no template
                is registered under it
        """

        self._validate_template_id(
            template_id
        )

        with self._lock:

            if template_id not in self._registry.templates:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError(
                        "Cannot unregister a template: no template is "
                        f"registered under template ID {template_id!r}."
                    )
                )

            updated = dict(
                self._registry.templates
            )

            del updated[template_id]

            self._replace_templates(
                updated
            )

    def find(

        self,

        template_id,

    ):
        """
        Find the template registered under a template ID.

        Args:
            template_id: The template ID to look up

        Returns:
            The matching template, or None if no template is
            registered under it
        """

        with self._lock:

            return self._registry.templates.get(
                template_id
            )

    def contains(

        self,

        template_id,

    ) -> bool:
        """
        Check whether a template is registered under a template ID.

        Args:
            template_id: The template ID to check

        Returns:
            True if a template is registered under the template ID,
            False otherwise
        """

        with self._lock:

            return template_id in self._registry.templates

    def list(

        self,

    ) -> tuple:
        """
        List every registered template.

        Returns:
            An immutable tuple of every registered template,
            preserving registration order
        """

        with self._lock:

            return tuple(
                self._registry.templates.values()
            )

    def snapshot(

        self,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistrySnapshot:
        """
        Take a snapshot of the registry's current state.

        Returns:
            An immutable snapshot carrying the current template
            count and every registered template's identifier,
            preserving registration order
        """

        with self._lock:

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistrySnapshot(
                    template_count=len(
                        self._registry.templates
                    ),

                    template_identifiers=tuple(
                        self._registry.templates.keys()
                    ),
                )
            )

    def _replace_templates(

        self,

        templates,

    ) -> None:

        self._registry = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistry(
                templates=MappingProxyType(
                    templates
                )
            )
        )

    def _validate_template_id(

        self,

        template_id,

    ) -> None:

        if (

            template_id is None

            or not template_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError(
                    "Cannot operate on a template with an empty or blank "
                    "template ID."
                )
            )

    def _validate_template(

        self,

        template,

    ) -> None:

        if template is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError(
                    "Cannot register a None template."
                )
            )

        if not isinstance(

            template,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError(
                    "Cannot register a template: template must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate."
                )
            )

        self._validate_template_id(
            template.template_id
        )
