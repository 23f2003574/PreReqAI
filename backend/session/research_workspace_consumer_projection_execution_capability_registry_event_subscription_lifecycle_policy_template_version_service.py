from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_version_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionHistory,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService:
    """
    Maintains the version history of consumer projection execution
    capability registry event subscription lifecycle policy
    templates, and manages rollback between previously published
    versions.

    The service's responsibility is version publication, lookup,
    history tracking, and rollback, not template registration,
    policy evaluation, lifecycle transition execution, persistence,
    logging, or event publication. It does NOT register templates,
    evaluate policies, execute lifecycle transitions, persist
    history, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an
      internal lock
    - Duplicate-free: No two versions published for the same
      template may share a version identifier
    - Order-preserving: Versions are listed in the order they were
      published
    - Non-destructive: Rollback changes which version is current
      without removing any version from history
    """

    def __init__(self):

        self._histories = {}

        self._lock = RLock()

    def publish(

        self,

        template_id,

        version,

    ) -> None:
        """
        Publish a new version for a template.

        Args:
            template_id: The identifier of the template to publish a
                version for
            version: The
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion
                to publish

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError:
                If the template ID is None or blank, the version is
                None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion,
                has an empty or blank version identifier, has a
                missing lifecycle policy, or a version with the same
                identifier has already been published for this
                template
        """

        self._validate_template_id(
            template_id
        )

        self._validate_version(
            version
        )

        with self._lock:

            existing = self._histories.get(
                template_id
            )

            if existing is not None and any(

                published.version == version.version

                for published

                in existing.versions
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError(
                        "Cannot publish a version: version "
                        f"{version.version!r} has already been published "
                        f"for template ID {template_id!r}."
                    )
                )

            previous_versions = (
                existing.versions
                if existing is not None
                else ()
            )

            self._histories[template_id] = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionHistory(
                    template_id=template_id,

                    current_version=version.version,

                    versions=previous_versions + (version,),
                )
            )

    def latest(

        self,

        template_id,

    ):
        """
        Find the current version for a template.

        Args:
            template_id: The template ID to look up

        Returns:
            The current
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion,
            or None if no version has been published for the
            template
        """

        with self._lock:

            history = self._histories.get(
                template_id
            )

        if history is None:

            return None

        return self._find_version(

            history,

            history.current_version,
        )

    def find(

        self,

        template_id,

        version,

    ):
        """
        Find a specific published version for a template.

        Args:
            template_id: The template ID to look up
            version: The version identifier to look up

        Returns:
            The matching
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion,
            or None if no such version has been published for the
            template
        """

        with self._lock:

            history = self._histories.get(
                template_id
            )

        if history is None:

            return None

        return self._find_version(

            history,

            version,
        )

    def history(

        self,

        template_id,

    ):
        """
        Read the full version history for a template.

        Args:
            template_id: The template ID to look up

        Returns:
            The template's immutable
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionHistory,
            or None if no version has been published for the
            template
        """

        with self._lock:

            return self._histories.get(
                template_id
            )

    def rollback(

        self,

        template_id,

        version,

    ) -> None:
        """
        Roll a template back to a previously published version.

        Rollback only changes which version is current; it never
        removes a version from history, including versions published
        after the version being rolled back to.

        Args:
            template_id: The identifier of the template to roll back
            version: The version identifier to roll back to

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError:
                If the template ID or version is None or blank, no
                version has ever been published for the template, or
                the version was never published for the template
        """

        self._validate_template_id(
            template_id
        )

        self._validate_version_identifier(
            version
        )

        with self._lock:

            existing = self._histories.get(
                template_id
            )

            if existing is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError(
                        "Cannot roll back template ID "
                        f"{template_id!r}: no version has ever been "
                        "published for it."
                    )
                )

            if self._find_version(existing, version) is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError(
                        f"Cannot roll back to version {version!r}: it was "
                        f"never published for template ID {template_id!r}."
                    )
                )

            self._histories[template_id] = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionHistory(
                    template_id=existing.template_id,

                    current_version=version,

                    versions=existing.versions,
                )
            )

    def _find_version(

        self,

        history,

        version,

    ):

        for published in history.versions:

            if published.version == version:

                return published

        return None

    def _validate_template_id(

        self,

        template_id,

    ) -> None:

        if (

            template_id is None

            or not template_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError(
                    "Cannot operate on a template with an empty or blank "
                    "template ID."
                )
            )

    def _validate_version_identifier(

        self,

        version,

    ) -> None:

        if (

            version is None

            or not version.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError(
                    "Cannot operate with an empty or blank version "
                    "identifier."
                )
            )

    def _validate_version(

        self,

        version,

    ) -> None:

        if version is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError(
                    "Cannot publish a None version."
                )
            )

        if not isinstance(

            version,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError(
                    "Cannot publish a version: version must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion."
                )
            )

        self._validate_version_identifier(
            version.version
        )

        if version.lifecycle_policy is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError(
                    "Cannot publish a version with a missing lifecycle "
                    "policy."
                )
            )
