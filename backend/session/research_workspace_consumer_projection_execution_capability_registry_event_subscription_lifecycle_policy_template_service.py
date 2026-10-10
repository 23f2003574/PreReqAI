from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_collection import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCollection,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService:
    """
    Maintains a registry of reusable consumer projection execution
    capability registry event subscription lifecycle policy
    templates, and instantiates lifecycle policies from them.

    The service's responsibility is template registration,
    replacement, removal, lookup, and instantiation, not policy
    evaluation, lifecycle transition execution, persistence,
    logging, or event publication. It does NOT evaluate policies,
    execute lifecycle transitions, persist templates, log, or
    publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an
      internal lock
    - Duplicate-free: No two registered templates may share a
      template ID
    - Order-preserving: Templates are listed in the order they were
      first registered
    """

    def __init__(self):

        self._collection = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCollection(
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
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError:
                If the template is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
                has an empty or blank template ID, has a missing
                lifecycle policy, or its template ID is already
                registered
        """

        self._validate_template(
            template
        )

        with self._lock:

            if template.template_id in self._collection.templates:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError(
                        "Cannot register a template: template ID "
                        f"{template.template_id!r} is already registered."
                    )
                )

            updated = dict(
                self._collection.templates
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
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError:
                If the template is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
                has an empty or blank template ID, has a missing
                lifecycle policy, or no template is registered under
                its template ID
        """

        self._validate_template(
            template
        )

        with self._lock:

            if template.template_id not in self._collection.templates:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError(
                        "Cannot replace a template: no template is "
                        f"registered under template ID {template.template_id!r}."
                    )
                )

            updated = dict(
                self._collection.templates
            )

            updated[template.template_id] = template

            self._replace_templates(
                updated
            )

    def remove(

        self,

        template_id,

    ) -> None:
        """
        Remove the template registered under a template ID.

        This is a no-op if no template with that ID is registered.

        Args:
            template_id: The template ID to remove
        """

        with self._lock:

            if template_id not in self._collection.templates:

                return

            updated = dict(
                self._collection.templates
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

            return self._collection.templates.get(
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

            return template_id in self._collection.templates

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
                self._collection.templates.values()
            )

    def instantiate(

        self,

        template_id,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy:
        """
        Instantiate a new lifecycle policy from a registered
        template.

        Args:
            template_id: The template ID to instantiate a lifecycle
                policy from

        Returns:
            A new lifecycle policy instance carrying the same
            allowed states and initial state as the template's
            lifecycle policy

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError:
                If no template is registered under the template ID
        """

        with self._lock:

            template = self._collection.templates.get(
                template_id
            )

        if template is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError(
                    "Cannot instantiate a lifecycle policy: no template is "
                    f"registered under template ID {template_id!r}."
                )
            )

        source = template.lifecycle_policy

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy(
                allowed_states=tuple(
                    source.allowed_states
                ),

                initial_state=source.initial_state,
            )
        )

    def _replace_templates(

        self,

        templates,

    ) -> None:

        self._collection = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCollection(
                templates=MappingProxyType(
                    templates
                )
            )
        )

    def _validate_template(

        self,

        template,

    ) -> None:

        if template is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError(
                    "Cannot register a None template."
                )
            )

        if not isinstance(

            template,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError(
                    "Cannot register a template: template must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate."
                )
            )

        if (

            template.template_id is None

            or not template.template_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError(
                    "Cannot register a template with an empty or blank "
                    "template ID."
                )
            )

        if template.lifecycle_policy is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError(
                    "Cannot register a template with a missing lifecycle "
                    "policy."
                )
            )
