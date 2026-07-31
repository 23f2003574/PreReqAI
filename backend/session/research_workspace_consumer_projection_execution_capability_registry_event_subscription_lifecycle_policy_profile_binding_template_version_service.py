from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_version_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionHistory,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionService:
    """
    Publishes and tracks immutable version snapshots of consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding templates, so a deployment or
    instantiation can target a stable revision instead of a
    template's mutable, current definition.

    The service's responsibility is version publication, lookup, and
    rollback, not template registration, membership management,
    parameter declaration, or persistence. It does NOT register
    templates, mutate template membership, declare parameters, mutate
    a published version, persist history externally, log, or publish
    events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two versions published for the same template
      may share a version identifier
    - Append-only: A published version is never replaced or removed;
      a rollback publishes a new version rather than reverting one
    - Chronological: Versions are listed in the order they were
      published
    """

    def __init__(self, template_registry, parameterization_service):
        """
        Args:
            template_registry: The registry used to snapshot a
                template's current member bindings at publish time.
                Any object exposing `find(template_id)`, returning an
                object with a `binding_ids` collection, is accepted
            parameterization_service: The service used to snapshot a
                template's declared parameters at publish time. Any
                object exposing `supported_parameters(template_id)`
                is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError:
                If the template registry or parameterization service
                is None
        """

        if template_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                "Cannot initialize binding template version service with a None template registry."
            )

        if parameterization_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                "Cannot initialize binding template version service with a None parameterization service."
            )

        self._template_registry = template_registry
        self._parameterization_service = parameterization_service
        self._histories = {}
        self._lock = RLock()

    def publish(
        self,
        template_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersion:
        """
        Publish a new version snapshot of a template's current member
        bindings and declared parameters.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError:
                If the template ID or version is None or blank, no
                template is registered under the template ID, or the
                version has already been published for the template
        """

        self._validate_identifier(template_id, "template ID")
        self._validate_identifier(version, "version")

        template = self._template_registry.find(template_id)

        if template is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                f"Cannot publish: no template is registered under template ID {template_id!r}."
            )

        with self._lock:
            existing_versions = self._existing_versions(template_id)

            if any(existing.version == version for existing in existing_versions):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                    f"Cannot publish: version {version!r} has already been published for template ID {template_id!r}."
                )

            snapshot = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersion(
                version=version,
                binding_ids=tuple(template.binding_ids),
                parameters=tuple(self._parameterization_service.supported_parameters(template_id)),
                created_at=datetime.now(timezone.utc),
            )

            self._histories[template_id] = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionHistory(
                template_id=template_id,
                current_version=version,
                versions=existing_versions + (snapshot,),
            )

            return snapshot

    def latest(
        self,
        template_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersion:
        """
        Look up a template's currently effective version.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError:
                If the template ID is None or blank, or no version has
                ever been published for the template
        """

        history = self.history(template_id)

        return self._find_version(history, history.current_version)

    def find(self, template_id: str, version: str):
        """
        Find a specific published version of a template.

        Returns:
            The matching version, or None if no version is registered
            under the template ID, or the version was never published
            for it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError:
                If the template ID or version is None or blank
        """

        self._validate_identifier(template_id, "template ID")
        self._validate_identifier(version, "version")

        with self._lock:
            history = self._histories.get(template_id)

        if history is None:
            return None

        return self._find_version(history, version)

    def history(
        self,
        template_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionHistory:
        """
        Get the complete version history of a template.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError:
                If the template ID is None or blank, or no version has
                ever been published for the template
        """

        self._validate_identifier(template_id, "template ID")

        with self._lock:
            history = self._histories.get(template_id)

        if history is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                f"Cannot get history: no version has ever been published for template ID {template_id!r}."
            )

        return history

    def rollback(
        self,
        template_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersion:
        """
        Roll a template back to a previously published version.

        The rollback publishes a new version, carrying the same
        member bindings and declared parameters as the target
        version, as the template's current version. No prior version
        is ever modified or removed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError:
                If the template ID or version is None or blank, no
                version has ever been published for the template, or
                the version was never published for it
        """

        self._validate_identifier(template_id, "template ID")
        self._validate_identifier(version, "version")

        with self._lock:
            history = self._histories.get(template_id)

            if history is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                    f"Cannot roll back: no version has ever been published for template ID {template_id!r}."
                )

            target = self._find_version(history, version)

            if target is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                    f"Cannot roll back: no version {version!r} has been published for template ID {template_id!r}."
                )

            restored = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersion(
                version=str(uuid4()),
                binding_ids=target.binding_ids,
                parameters=target.parameters,
                created_at=datetime.now(timezone.utc),
            )

            self._histories[template_id] = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionHistory(
                template_id=template_id,
                current_version=restored.version,
                versions=history.versions + (restored,),
            )

            return restored

    def _existing_versions(self, template_id: str) -> tuple:
        history = self._histories.get(template_id)

        return history.versions if history is not None else ()

    def _find_version(self, history, version: str):
        for existing in history.versions:
            if existing.version == version:
                return existing

        return None

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                f"Cannot operate with an empty or blank {label}."
            )
