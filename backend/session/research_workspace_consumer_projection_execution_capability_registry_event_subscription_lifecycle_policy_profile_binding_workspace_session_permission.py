from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_authorization_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError,
)

VALID_SESSION_OPERATIONS = (
    "START",
    "FINISH",
    "CANCEL",
    "RESTORE",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPermission:
    """
    Immutable grant allowing a role to perform a specific lifecycle
    operation on a consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    execution session.

    The permission is a value object only. It performs no
    authorization decision. Granting, revoking, and checking
    permissions are the responsibility of a session authorization
    service.

    Attributes:
        permission_id: The permission's unique identifier
        operation: The lifecycle operation this permission covers, one
            of "START", "FINISH", "CANCEL", or "RESTORE"
        role: The role this permission is granted to
    """

    permission_id: str

    operation: str

    role: str

    def __post_init__(self):
        if self.permission_id is None or not self.permission_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError(
                "Cannot build a session permission with an empty or blank permission ID."
            )

        if self.operation is None or not isinstance(self.operation, str) or not self.operation.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError(
                "Cannot build a session permission with an empty, blank, or non-string operation."
            )

        if self.operation not in VALID_SESSION_OPERATIONS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError(
                f"Invalid session permission operation {self.operation!r}. Must be one of "
                f"{VALID_SESSION_OPERATIONS!r}."
            )

        if self.role is None or not self.role.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuthorizationError(
                "Cannot build a session permission with an empty or blank role."
            )
