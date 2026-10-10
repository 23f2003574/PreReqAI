from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_release import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRelease,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_release_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_release_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseService:
    """
    Promotes consumer projection execution capability registry event
    subscription lifecycle policy profile binding versions through a
    controlled release lifecycle (DRAFT -> RELEASED -> RETIRED), so
    that only approved binding configuration versions can be
    promoted into deployment. Only a (binding, version) pair
    currently holding RELEASED status is deployable.

    The service's responsibility is release status tracking, not
    binding creation, profile version publication, or deployment
    itself. It does NOT create bindings, publish profile versions,
    deploy bindings, mutate the binding registry or version history,
    persist state externally, log, or publish events. Every
    transition produces a new, immutable release record; no release
    record is ever mutated.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Deterministic: Same sequence of operations always produces the
      same observable state, including the release identifier itself
    - Forward-only: A (binding, version) pair may only move DRAFT ->
      RELEASED -> RETIRED, never backward or sideways
    - One active release per (binding_id, version): Re-releasing an
      already released or already retired version is rejected
    - Append-only: Every transition appends a new record to the
      release history; no earlier record is ever mutated or removed
    """

    def __init__(self, binding_registry, version_service):
        """
        Args:
            binding_registry: The registry used to resolve a binding
                ID to its profile ID. Any object exposing
                `find(binding_id)` is accepted
            version_service: The version service used to verify a
                version was published for the binding's profile. Any
                object exposing `find(profile_id, version)` is
                accepted
        """

        if binding_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError(
                "Cannot initialize release service with a None binding registry."
            )

        if version_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError(
                "Cannot initialize release service with a None version service."
            )

        self._binding_registry = binding_registry
        self._version_service = version_service
        self._releases = {}
        self._lock = RLock()

    def release(
        self,
        binding_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseResult:
        """
        Release a binding configuration version, promoting it from
        DRAFT to RELEASED.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError:
                If the binding ID or version is None or blank, no
                binding is registered under the binding ID, no
                version was published for the binding's profile, or
                the version has already been released or retired
        """

        key = self._key(binding_id, version)

        with self._lock:
            existing = self._releases.get(key)

            if existing is not None:
                if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.RELEASED:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError(
                        f"Cannot release version {version!r} of binding ID {binding_id!r}: it has already been released."
                    )

                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError(
                    f"Cannot release version {version!r} of binding ID {binding_id!r}: it is retired and cannot be released again."
                )

            previous_status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.DRAFT

            new_release = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRelease(
                release_id=self._generate_release_id(binding_id, version),
                binding_id=binding_id,
                version=version,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.RELEASED,
                released_at=datetime.now(timezone.utc),
            )

            self._releases[key] = new_release

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseResult(
                previous_status=previous_status,
                current_status=new_release.status,
                release=new_release,
            )

    def retire(
        self,
        binding_id: str,
        version: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseResult:
        """
        Retire a released binding configuration version, demoting it
        from RELEASED to RETIRED.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError:
                If the binding ID or version is None or blank, no
                binding is registered under the binding ID, no
                version was published for the binding's profile, the
                version has never been released, or it has already
                been retired
        """

        key = self._key(binding_id, version)

        with self._lock:
            existing = self._releases.get(key)

            if existing is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError(
                    f"Cannot retire version {version!r} of binding ID {binding_id!r}: it has never been released."
                )

            if existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.RETIRED:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError(
                    f"Cannot retire version {version!r} of binding ID {binding_id!r}: it has already been retired."
                )

            new_release = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRelease(
                release_id=existing.release_id,
                binding_id=binding_id,
                version=version,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.RETIRED,
                released_at=existing.released_at,
            )

            self._releases[key] = new_release

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseResult(
                previous_status=existing.status,
                current_status=new_release.status,
                release=new_release,
            )

    def latest_release(self, binding_id: str):
        """
        Find the most recently released, currently active release
        for a binding.

        Returns:
            The release record with status RELEASED and the latest
            released_at for the binding, or None if the binding has
            no currently released version

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError:
                If the binding ID is None or blank, or no binding is
                registered under it
        """

        self._resolve_binding(binding_id)

        with self._lock:
            candidates = [
                release
                for release in self._releases.values()
                if (
                    release.binding_id == binding_id
                    and release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.RELEASED
                )
            ]

        if not candidates:
            return None

        return max(candidates, key=lambda release: release.released_at)

    def is_released(self, binding_id: str, version: str) -> bool:
        """
        Check whether a (binding, version) pair currently holds
        RELEASED status. Only a version for which this returns True
        is deployable.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError:
                If the binding ID or version is None or blank, no
                binding is registered under the binding ID, or no
                version was published for the binding's profile
        """

        key = self._key(binding_id, version)

        with self._lock:
            existing = self._releases.get(key)

        return (
            existing is not None
            and existing.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.RELEASED
        )

    def _key(self, binding_id: str, version: str):
        binding = self._resolve_binding(binding_id)

        self._validate_identifier(version, "version")

        if self._version_service.find(binding.profile_id, version) is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError(
                f"Cannot operate: version {version!r} was not found for binding ID {binding_id!r}."
            )

        return (binding_id, version)

    def _resolve_binding(self, binding_id: str):
        self._validate_identifier(binding_id, "binding ID")

        binding = self._binding_registry.find(binding_id)

        if binding is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError(
                f"Cannot operate: no binding is registered under binding ID {binding_id!r}."
            )

        return binding

    def _generate_release_id(self, binding_id: str, version: str) -> str:
        return f"release::{binding_id}::{version}"

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError(
                f"Cannot operate with an empty or blank {label}."
            )
