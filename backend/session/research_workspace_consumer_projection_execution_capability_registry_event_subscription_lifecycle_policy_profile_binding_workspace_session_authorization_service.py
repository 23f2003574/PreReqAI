from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_authorization_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_permission import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPermission,
    VALID_SESSION_OPERATIONS,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_authorization_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationService:
    """
    Grants and checks role-based permission to perform lifecycle
    operations on a consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    execution session, so a lifecycle action never runs on behalf of a
    role that was never granted it.

    The service's responsibility is the authorization decision, not
    session lifecycle or principal identity. It does NOT start,
    finish, cancel, or restore a session itself; a caller is expected
    to call authorize() immediately before performing a lifecycle
    operation, and to decline to perform it when the returned result
    is not authorized. It also does NOT resolve a principal to a role
    itself; principal is treated as the role to check directly.

    Behavior:
    - A role has no permissions until they are explicitly granted; any
      operation not explicitly granted to a role is denied by default
    - Permissions are operation-specific: granting a role permission
      for one operation does not grant it permission for any other
    - Granting a role a permission it already holds for an operation
      replaces the prior grant
    - revoke() removes a single (role, operation) grant

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._permissions_by_role = {}
        self._lock = RLock()

    def authorize(
        self, session_id: str, operation: str, principal: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationResult:
        """
        Decide whether a principal may perform a lifecycle operation
        on a session, immediately before that operation runs.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError:
                If session_id, operation, or principal is None or
                blank, or operation is not one of
                VALID_SESSION_OPERATIONS
        """

        self._validate_id(session_id, "session ID")
        self._validate_operation(operation)
        self._validate_id(principal, "principal")

        with self._lock:
            role_permissions = self._permissions_by_role.get(principal, {})

            if operation in role_permissions:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationResult(
                    authorized=True,
                )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationResult(
                authorized=False,
                reason=f"role {principal!r} has no {operation!r} permission on session ID {session_id!r}.",
            )

    def grant(
        self, role: str, permission: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPermission:
        """
        Grant a role permission to perform a lifecycle operation,
        replacing any prior grant of that same operation to that role.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError:
                If role is None or blank, or permission is not one of
                VALID_SESSION_OPERATIONS
        """

        self._validate_id(role, "role")
        self._validate_operation(permission)

        granted = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPermission(
            permission_id=str(uuid4()),
            operation=permission,
            role=role,
        )

        with self._lock:
            self._permissions_by_role.setdefault(role, {})[permission] = granted

            return granted

    def revoke(self, role: str, permission: str) -> None:
        """
        Revoke a role's permission to perform a lifecycle operation.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError:
                If role is None or blank, permission is not one of
                VALID_SESSION_OPERATIONS, or the role does not
                currently hold that permission
        """

        self._validate_id(role, "role")
        self._validate_operation(permission)

        with self._lock:
            role_permissions = self._permissions_by_role.get(role, {})

            if permission not in role_permissions:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError(
                    f"Role {role!r} does not hold {permission!r} permission."
                )

            del role_permissions[permission]

    def permissions(self, role: str) -> tuple:
        """
        List every permission currently granted to a role.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError:
                If role is None or blank
        """

        self._validate_id(role, "role")

        with self._lock:
            return tuple(self._permissions_by_role.get(role, {}).values())

    def _validate_operation(self, operation: str) -> None:
        if operation is None or not isinstance(operation, str) or not operation.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError(
                "Cannot operate with an empty, blank, or non-string operation."
            )

        if operation not in VALID_SESSION_OPERATIONS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError(
                f"Invalid operation {operation!r}. Must be one of {VALID_SESSION_OPERATIONS!r}."
            )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError(
                f"Cannot operate with an empty or blank {label}."
            )
