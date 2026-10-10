from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_override import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverride,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_override_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_override_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideService:
    """
    Manages temporary profile assignment overrides to target contexts without
    modifying underlying registrations.

    This service is useful for environment-, tenant-, or runtime-specific adjustments.
    Multiple overrides can be registered for a target, and the highest-priority active
    override wins.

    The service is:
    - Thread-safe: Mutex-guarded read and write operations
    - Deterministic: Ties in priority are broken deterministically by override ID alphabetically
    - Fallback-supported: Falls back to the standard profile assignment if no active overrides exist
    """

    def __init__(self, assignment_registry_service, profile_service):
        """
        Args:
            assignment_registry_service: Any object exposing find(target_id) to look up normal assignments
            profile_service: Any object exposing contains(profile_id) to verify profile existence
        """
        if assignment_registry_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError(
                "Cannot initialize override service with a None assignment registry service."
            )

        if profile_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError(
                "Cannot initialize override service with a None profile service."
            )

        self._assignment_registry_service = assignment_registry_service
        self._profile_service = profile_service
        self._overrides = {}  # override_id -> override
        # Track insertion order for deterministic listing/resolutions
        self._override_order = []
        self._lock = RLock()

    def add_override(
        self,
        override: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverride,
    ) -> None:
        """
        Registers a new profile assignment override.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError:
                If override is None, is not of the correct class type, override ID is duplicate,
                or the referenced profile ID is unknown/unregistered.
        """
        if override is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError(
                "Cannot add a None override."
            )

        if not isinstance(
            override,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverride,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError(
                "Must be a ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverride instance."
            )

        with self._lock:
            if override.override_id in self._overrides:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError(
                    f"Override ID {override.override_id!r} is already registered."
                )

            if not self._profile_service.contains(override.profile_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError(
                    f"Profile ID {override.profile_id!r} is unknown/unregistered."
                )

            self._overrides[override.override_id] = override
            self._override_order.append(override.override_id)

    def remove_override(self, override_id: str) -> None:
        """
        Removes the override associated with override_id.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError:
                If override_id is None/blank or the override does not exist.
        """
        self._validate_id(override_id, "override ID")

        with self._lock:
            if override_id not in self._overrides:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError(
                    f"Override ID {override_id!r} is not registered."
                )

            del self._overrides[override_id]
            self._override_order.remove(override_id)

    def resolve_effective(
        self, target_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideResult:
        """
        Resolves the effective profile ID for target_id.
        Active overrides with highest priority win, falling back to normal assignment.

        Ties in priority are resolved by comparing override_id alphabetically.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError:
                If target_id is None or blank.
        """
        self._validate_id(target_id, "target ID")

        with self._lock:
            active_overrides = [
                ov
                for ov in self._overrides.values()
                if ov.target_id == target_id and ov.active
            ]

            if active_overrides:
                # Sort by priority descending, then by override_id alphabetically ascending
                # to guarantee deterministic tie-breaking
                active_overrides.sort(key=lambda x: (-x.priority, x.override_id))
                highest = active_overrides[0]
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideResult(
                    effective_profile_id=highest.profile_id,
                    override_applied=True,
                )

            # Fallback to standard assignment
            normal_assignment = self._assignment_registry_service.find(target_id)
            if normal_assignment is not None:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideResult(
                    effective_profile_id=normal_assignment.profile_id,
                    override_applied=False,
                )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideResult(
                effective_profile_id=None,
                override_applied=False,
            )

    def list_overrides(self, target_id: str) -> tuple:
        """
        Lists all overrides (active or inactive) registered for target_id,
        preserving registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError:
                If target_id is None or blank.
        """
        self._validate_id(target_id, "target ID")

        with self._lock:
            result = []
            for ov_id in self._override_order:
                ov = self._overrides[ov_id]
                if ov.target_id == target_id:
                    result.append(ov)
            return tuple(result)

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideError(
                f"Cannot perform override operation with an empty or blank {label}."
            )
