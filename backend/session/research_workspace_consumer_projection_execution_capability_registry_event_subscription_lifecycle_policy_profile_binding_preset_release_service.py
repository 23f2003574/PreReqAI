from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_release import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRelease,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_release_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_release_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseService:
    """
    Promotes consumer projection execution capability registry event
    subscription lifecycle policy profile binding preset versions
    through a controlled release lifecycle (DRAFT -> RELEASED ->
    RETIRED), so that only approved preset version snapshots can be
    promoted into deployment. Only a (preset, version) pair currently
    holding RELEASED status is deployable.

    The service's responsibility is release status tracking, not
    preset creation, membership management, version publication, or
    deployment itself. It does NOT create presets, mutate preset
    membership, publish preset versions, deploy presets, mutate the
    preset registry or version history, persist state externally,
    log, or publish events. Every transition produces a new,
    immutable release record; no release record is ever mutated.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Deterministic: Same sequence of operations always produces the
      same observable state, including the release identifier itself
    - Forward-only: A (preset, version) pair may only move DRAFT ->
      RELEASED -> RETIRED, never backward or sideways
    - One active release per (preset_id, version): Re-releasing an
      already released or already retired version is rejected
    - Append-only: Every transition appends a new record to the
      release history; no earlier record is ever mutated or removed
    """

    def __init__(self, preset_registry, preset_version_service):
        """
        Args:
            preset_registry: The registry used to verify a preset
                exists. Any object exposing `find(preset_id)` is
                accepted
            preset_version_service: The version service used to
                verify a version was published for the preset. Any
                object exposing `find(preset_id, version)` is
                accepted
        """

        if preset_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError(
                "Cannot initialize release service with a None preset registry."
            )

        if preset_version_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError(
                "Cannot initialize release service with a None preset version service."
            )

        self._preset_registry = preset_registry
        self._preset_version_service = preset_version_service
        self._releases = {}
        self._lock = RLock()

    def release(
        self,
        preset_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseResult:
        """
        Release a preset version, promoting it from DRAFT to
        RELEASED.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError:
                If the preset ID or version is None or blank, no
                preset is registered under the preset ID, no version
                was published for the preset, or the version has
                already been released or retired
        """

        key = self._key(preset_id, version)

        with self._lock:
            existing = self._releases.get(key)

            if existing is not None:
                if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.RELEASED:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError(
                        f"Cannot release version {version!r} of preset ID {preset_id!r}: it has already been released."
                    )

                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError(
                    f"Cannot release version {version!r} of preset ID {preset_id!r}: it is retired and cannot be released again."
                )

            previous_status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.DRAFT

            new_release = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRelease(
                release_id=self._generate_release_id(preset_id, version),
                preset_id=preset_id,
                version=version,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.RELEASED,
                released_at=datetime.now(timezone.utc),
            )

            self._releases[key] = new_release

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseResult(
                previous_status=previous_status,
                current_status=new_release.status,
                release=new_release,
            )

    def retire(
        self,
        preset_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseResult:
        """
        Retire a released preset version, demoting it from RELEASED
        to RETIRED.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError:
                If the preset ID or version is None or blank, no
                preset is registered under the preset ID, no version
                was published for the preset, the version has never
                been released, or it has already been retired
        """

        key = self._key(preset_id, version)

        with self._lock:
            existing = self._releases.get(key)

            if existing is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError(
                    f"Cannot retire version {version!r} of preset ID {preset_id!r}: it has never been released."
                )

            if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.RETIRED:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError(
                    f"Cannot retire version {version!r} of preset ID {preset_id!r}: it has already been retired."
                )

            new_release = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRelease(
                release_id=existing.release_id,
                preset_id=preset_id,
                version=version,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.RETIRED,
                released_at=existing.released_at,
            )

            self._releases[key] = new_release

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseResult(
                previous_status=existing.status,
                current_status=new_release.status,
                release=new_release,
            )

    def latest_release(self, preset_id: str):
        """
        Find the most recently released, currently active release
        for a preset.

        Returns:
            The release record with status RELEASED and the latest
            released_at for the preset, or None if the preset has no
            currently released version

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError:
                If the preset ID is None or blank, or no preset is
                registered under it
        """

        self._resolve_preset(preset_id)

        with self._lock:
            candidates = [
                release
                for release in self._releases.values()
                if (
                    release.preset_id == preset_id
                    and release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.RELEASED
                )
            ]

        if not candidates:
            return None

        return max(candidates, key=lambda release: release.released_at)

    def is_released(self, preset_id: str, version: str) -> bool:
        """
        Check whether a (preset, version) pair currently holds
        RELEASED status. Only a version for which this returns True
        is deployable.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError:
                If the preset ID or version is None or blank, no
                preset is registered under the preset ID, or no
                version was published for the preset
        """

        key = self._key(preset_id, version)

        with self._lock:
            existing = self._releases.get(key)

        return (
            existing is not None
            and existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus.RELEASED
        )

    def _key(self, preset_id: str, version: str):
        self._resolve_preset(preset_id)

        self._validate_identifier(version, "version")

        if self._preset_version_service.find(preset_id, version) is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError(
                f"Cannot operate: version {version!r} was not found for preset ID {preset_id!r}."
            )

        return (preset_id, version)

    def _resolve_preset(self, preset_id: str):
        self._validate_identifier(preset_id, "preset ID")

        preset = self._preset_registry.find(preset_id)

        if preset is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError(
                f"Cannot operate: no preset is registered under preset ID {preset_id!r}."
            )

        return preset

    def _generate_release_id(self, preset_id: str, version: str) -> str:
        return f"release::{preset_id}::{version}"

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError(
                f"Cannot operate with an empty or blank {label}."
            )
