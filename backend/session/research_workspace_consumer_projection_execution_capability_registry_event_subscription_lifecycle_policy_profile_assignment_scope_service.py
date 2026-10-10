from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_scope import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScope,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_scope_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_scoped_assignment import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileScopedAssignment,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeService:
    """
    Manages scoped assignments linking registered policy profiles to targets
    under specific environments, tenants, or namespaces.

    The service resolves assignments by exact scope match first, falling back to
    global target assignments. It maintains thread safety and enforces that there is
    at most one assignment per target/scope pair.
    """

    def __init__(self, assignment_registry_service, profile_service):
        """
        Args:
            assignment_registry_service: Any object exposing find(target_id)
            profile_service: Any object exposing contains(profile_id)
        """
        if assignment_registry_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError(
                "Cannot initialize scope service with a None assignment registry service."
            )

        if profile_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError(
                "Cannot initialize scope service with a None profile service."
            )

        self._assignment_registry_service = assignment_registry_service
        self._profile_service = profile_service
        self._assignments = {}  # (target_id, scope) -> ScopedAssignment
        self._assignment_keys = []  # Track insertion order
        self._lock = RLock()

    def assign(
        self,
        target_id: str,
        profile_id: str,
        scope: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScope,
    ) -> None:
        """
        Assigns a profile to a target under a scope.

        If a scoped assignment already exists for the target and scope:
        - If the profile ID is the same, raises a duplicate assignment error.
        - If the profile ID is different, replaces the existing assignment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError:
                If target_id, profile_id, or scope is invalid/blank, the profile ID is duplicate,
                or the profile is unknown/unregistered.
        """
        self._validate_id(target_id, "target ID")
        self._validate_id(profile_id, "profile ID")
        self._validate_scope(scope)

        with self._lock:
            if not self._profile_service.contains(profile_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError(
                    f"Profile ID {profile_id!r} is unknown/unregistered."
                )

            key = (target_id, scope)
            if key in self._assignments:
                existing = self._assignments[key]
                if existing.profile_id == profile_id:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError(
                        f"Duplicate assignment: target ID {target_id!r} under scope ID {scope.scope_id!r} "
                        f"already has profile ID {profile_id!r} assigned."
                    )
                # Fallthrough: replace existing
                new_assignment = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileScopedAssignment(
                    target_id=target_id,
                    profile_id=profile_id,
                    scope=scope,
                )
                self._assignments[key] = new_assignment
            else:
                new_assignment = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileScopedAssignment(
                    target_id=target_id,
                    profile_id=profile_id,
                    scope=scope,
                )
                self._assignments[key] = new_assignment
                self._assignment_keys.append(key)

    def unassign(
        self,
        target_id: str,
        scope: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScope,
    ) -> None:
        """
        Removes the scoped assignment for target_id under scope.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError:
                If target_id or scope is invalid/blank, or no scoped assignment is registered.
        """
        self._validate_id(target_id, "target ID")
        self._validate_scope(scope)

        with self._lock:
            key = (target_id, scope)
            if key not in self._assignments:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError(
                    f"No scoped assignment registered for target ID {target_id!r} under scope ID {scope.scope_id!r}."
                )
            del self._assignments[key]
            self._assignment_keys.remove(key)

    def resolve(
        self,
        target_id: str,
        scope: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScope,
    ) -> str | None:
        """
        Resolves the profile ID for target_id in scope.
        Tries exact scope match first, falling back to global assignment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError:
                If target_id or scope is invalid/blank.
        """
        self._validate_id(target_id, "target ID")
        self._validate_scope(scope)

        with self._lock:
            key = (target_id, scope)
            if key in self._assignments:
                return self._assignments[key].profile_id

            # Fallback to global registry assignment
            global_assignment = self._assignment_registry_service.find(target_id)
            if global_assignment is not None:
                return global_assignment.profile_id

            return None

    def list(self, target_id: str) -> tuple:
        """
        Lists all scoped assignments registered for target_id, preserving registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError:
                If target_id is None or blank.
        """
        self._validate_id(target_id, "target ID")

        with self._lock:
            result = []
            for key in self._assignment_keys:
                tgt_id, sc = key
                if tgt_id == target_id:
                    result.append(self._assignments[key])
            return tuple(result)

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError(
                f"Cannot perform scope operation with an empty or blank {label}."
            )

    def _validate_scope(
        self,
        scope: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScope,
    ) -> None:
        if scope is None or not isinstance(
            scope,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScope,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScopeError(
                "Scope must be a valid ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentScope instance."
            )
