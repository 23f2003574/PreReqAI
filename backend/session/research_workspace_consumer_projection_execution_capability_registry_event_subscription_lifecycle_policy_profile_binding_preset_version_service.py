from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_version_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionHistory,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionService:
    """
    Publishes and tracks immutable version snapshots of consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding presets, so a deployment or
    instantiation can target a stable revision instead of a preset's
    mutable, current definition.

    The service's responsibility is version publication, lookup, and
    rollback, not preset registration, membership management,
    parameter declaration, or persistence. It does NOT register
    presets, mutate preset membership, declare parameters, mutate a
    published version, persist history externally, log, or publish
    events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two versions published for the same preset
      may share a version identifier
    - Append-only: A published version is never replaced or removed;
      a rollback publishes a new version rather than reverting one
    - Chronological: Versions are listed in the order they were
      published
    """

    def __init__(self, preset_registry, parameterization_service):
        """
        Args:
            preset_registry: The registry used to snapshot a preset's
                current member binding templates at publish time. Any
                object exposing `find(preset_id)`, returning an
                object with a `binding_template_ids` collection, is
                accepted
            parameterization_service: The service used to snapshot a
                preset's declared parameters at publish time. Any
                object exposing `supported_parameters(preset_id)` is
                accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError:
                If the preset registry or parameterization service is
                None
        """

        if preset_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                "Cannot initialize binding preset version service with a None preset registry."
            )

        if parameterization_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                "Cannot initialize binding preset version service with a None parameterization service."
            )

        self._preset_registry = preset_registry
        self._parameterization_service = parameterization_service
        self._histories = {}
        self._lock = RLock()

    def publish(
        self,
        preset_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersion:
        """
        Publish a new version snapshot of a preset's current member
        binding templates and declared parameters.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError:
                If the preset ID or version is None or blank, no
                preset is registered under the preset ID, or the
                version has already been published for the preset
        """

        self._validate_identifier(preset_id, "preset ID")
        self._validate_identifier(version, "version")

        preset = self._preset_registry.find(preset_id)

        if preset is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                f"Cannot publish: no preset is registered under preset ID {preset_id!r}."
            )

        with self._lock:
            existing_versions = self._existing_versions(preset_id)

            if any(existing.version == version for existing in existing_versions):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                    f"Cannot publish: version {version!r} has already been published for preset ID {preset_id!r}."
                )

            snapshot = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersion(
                version=version,
                template_ids=tuple(preset.binding_template_ids),
                parameters=tuple(self._parameterization_service.supported_parameters(preset_id)),
                created_at=datetime.now(timezone.utc),
            )

            self._histories[preset_id] = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionHistory(
                preset_id=preset_id,
                current_version=version,
                versions=existing_versions + (snapshot,),
            )

            return snapshot

    def latest(
        self,
        preset_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersion:
        """
        Look up a preset's currently effective version.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError:
                If the preset ID is None or blank, or no version has
                ever been published for the preset
        """

        history = self.history(preset_id)

        return self._find_version(history, history.current_version)

    def find(self, preset_id: str, version: str):
        """
        Find a specific published version of a preset.

        Returns:
            The matching version, or None if no preset is registered
            under the preset ID, or the version was never published
            for it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError:
                If the preset ID or version is None or blank
        """

        self._validate_identifier(preset_id, "preset ID")
        self._validate_identifier(version, "version")

        with self._lock:
            history = self._histories.get(preset_id)

        if history is None:
            return None

        return self._find_version(history, version)

    def history(
        self,
        preset_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionHistory:
        """
        Get the complete version history of a preset.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError:
                If the preset ID is None or blank, or no version has
                ever been published for the preset
        """

        self._validate_identifier(preset_id, "preset ID")

        with self._lock:
            history = self._histories.get(preset_id)

        if history is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                f"Cannot get history: no version has ever been published for preset ID {preset_id!r}."
            )

        return history

    def rollback(
        self,
        preset_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersion:
        """
        Roll a preset back to a previously published version.

        The rollback publishes a new version, carrying the same
        member binding templates and declared parameters as the
        target version, as the preset's current version. No prior
        version is ever modified or removed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError:
                If the preset ID or version is None or blank, no
                version has ever been published for the preset, or
                the version was never published for it
        """

        self._validate_identifier(preset_id, "preset ID")
        self._validate_identifier(version, "version")

        with self._lock:
            history = self._histories.get(preset_id)

            if history is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                    f"Cannot roll back: no version has ever been published for preset ID {preset_id!r}."
                )

            target = self._find_version(history, version)

            if target is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                    f"Cannot roll back: no version {version!r} has been published for preset ID {preset_id!r}."
                )

            restored = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersion(
                version=str(uuid4()),
                template_ids=target.template_ids,
                parameters=target.parameters,
                created_at=datetime.now(timezone.utc),
            )

            self._histories[preset_id] = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionHistory(
                preset_id=preset_id,
                current_version=restored.version,
                versions=history.versions + (restored,),
            )

            return restored

    def _existing_versions(self, preset_id: str) -> tuple:
        history = self._histories.get(preset_id)

        return history.versions if history is not None else ()

    def _find_version(self, history, version: str):
        for existing in history.versions:
            if existing.version == version:
                return existing

        return None

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                f"Cannot operate with an empty or blank {label}."
            )
