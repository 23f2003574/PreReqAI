from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_version_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionResult,
)

_LATEST_SELECTOR = "latest"


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionService:
    """
    Resolves the profile version a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding currently targets, allowing capabilities to pin a
    specific released version or automatically track the profile's
    latest released version.

    The service's responsibility is version selection and
    resolution, not binding creation, profile publication, or
    release management. It does NOT create bindings, publish
    versions, release or retire versions, mutate the binding
    registry, persist state externally, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Two modes: A binding either tracks the latest released version
      (the default, until pinned) or is pinned to a single released
      version
    - Released-only: Only a version currently holding RELEASED status
      can ever be resolved
    - Deterministic: Same binding state and release state always
      produce the same resolution
    """

    def __init__(
        self,
        binding_registry,
        version_service,
        release_service,
    ):
        """
        Args:
            binding_registry: The registry used to resolve a binding
                ID to its profile ID. Any object exposing
                `find(binding_id)` is accepted
            version_service: The version service used to verify a
                version was published. Any object exposing
                `find(profile_id, version)` is accepted
            release_service: The release service used to verify a
                version is released and to resolve the latest release.
                Any object exposing `is_released(profile_id, version)`
                and `latest_release(profile_id)` is accepted
        """

        if binding_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError(
                "Cannot initialize binding version service with a None binding registry."
            )

        if version_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError(
                "Cannot initialize binding version service with a None version service."
            )

        if release_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError(
                "Cannot initialize binding version service with a None release service."
            )

        self._binding_registry = binding_registry
        self._version_service = version_service
        self._release_service = release_service
        self._selections = {}
        self._lock = RLock()

    def resolve_version(
        self,
        binding_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionResult:
        """
        Resolve the version a binding currently targets.

        A pinned binding always resolves to the version it was
        pinned to. A binding following the latest release (the
        default until pinned) resolves to the profile's currently
        released version, or fails to resolve if none is released.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError:
                If the binding ID is None or blank, or no binding is
                registered under it
        """

        binding = self._resolve_binding(binding_id)

        with self._lock:
            selection = self._selections.get(binding_id)

        if selection is not None and selection.version_selector != _LATEST_SELECTOR:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionResult(
                resolved=True,
                version=selection.resolved_version,
            )

        latest_release = self._release_service.latest_release(binding.profile_id)

        if latest_release is None:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionResult(
                resolved=False,
                version=None,
            )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionResult(
            resolved=True,
            version=latest_release.version,
        )

    def pin_version(self, binding_id: str, version: str) -> None:
        """
        Pin a binding to a specific released profile version.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError:
                If the binding ID or version is None or blank, no
                binding is registered under the binding ID, the
                version was never published for the bound profile, or
                the version is not currently released
        """

        binding = self._resolve_binding(binding_id)
        self._validate_identifier(version, "version")

        if self._version_service.find(binding.profile_id, version) is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError(
                f"Cannot pin version {version!r}: it was never published for profile ID {binding.profile_id!r}."
            )

        if not self._release_service.is_released(binding.profile_id, version):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError(
                f"Cannot pin version {version!r}: it is not currently released for profile ID {binding.profile_id!r}."
            )

        with self._lock:
            self._selections[binding_id] = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersion(
                binding_id=binding_id,
                version_selector=version,
                resolved_version=version,
            )

    def follow_latest(self, binding_id: str) -> None:
        """
        Switch a binding to automatically track its bound profile's
        latest released version.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError:
                If the binding ID is None or blank, or no binding is
                registered under it
        """

        self._resolve_binding(binding_id)

        with self._lock:
            self._selections[binding_id] = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersion(
                binding_id=binding_id,
                version_selector=_LATEST_SELECTOR,
                resolved_version=None,
            )

    def is_pinned(self, binding_id: str) -> bool:
        """
        Check whether a binding is currently pinned to a specific
        version, as opposed to following the latest release.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError:
                If the binding ID is None or blank, or no binding is
                registered under it
        """

        self._resolve_binding(binding_id)

        with self._lock:
            selection = self._selections.get(binding_id)

        return selection is not None and selection.version_selector != _LATEST_SELECTOR

    def _resolve_binding(self, binding_id: str):
        self._validate_identifier(binding_id, "binding ID")

        binding = self._binding_registry.find(binding_id)

        if binding is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError(
                f"Cannot operate: no binding is registered under binding ID {binding_id!r}."
            )

        return binding

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError(
                f"Cannot operate with an empty or blank {label}."
            )
