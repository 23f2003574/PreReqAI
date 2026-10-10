from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_exception_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError,
)

VALID_SESSION_POLICY_EXCEPTION_SCOPES = (
    "MAX_RUNTIME",
    "MAX_IDLE",
    "ALLOW_RESTORE",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyException:
    """
    Immutable, auditable record of a temporary request to override
    one aspect of the session policy governing a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace execution session, without modifying
    the base policy itself.

    The exception is a value object only. It performs no approval,
    revocation, or expiration enforcement. Requesting, approving,
    revoking, and validating exceptions are the responsibility of a
    session policy exception service.

    Attributes:
        exception_id: The exception's unique identifier
        session_id: The identifier of the session this exception was
            requested for
        policy_id: The identifier of the base policy this exception
            temporarily overrides
        scope: Which aspect of the base policy this exception
            overrides, one of "MAX_RUNTIME", "MAX_IDLE", or
            "ALLOW_RESTORE"
        expires_at: When this exception stops being usable, regardless
            of whether it was approved
    """

    exception_id: str

    session_id: str

    policy_id: str

    scope: str

    expires_at: datetime

    def __post_init__(self):
        if self.exception_id is None or not self.exception_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                "Cannot build a session policy exception with an empty or blank exception ID."
            )

        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                "Cannot build a session policy exception with an empty or blank session ID."
            )

        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                "Cannot build a session policy exception with an empty or blank policy ID."
            )

        if self.scope is None or not isinstance(self.scope, str) or not self.scope.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                "Cannot build a session policy exception with an empty, blank, or non-string scope."
            )

        if self.scope not in VALID_SESSION_POLICY_EXCEPTION_SCOPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                f"Invalid session policy exception scope {self.scope!r}. Must be one of "
                f"{VALID_SESSION_POLICY_EXCEPTION_SCOPES!r}."
            )

        if self.expires_at is None or not isinstance(self.expires_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyExceptionError(
                "Cannot build a session policy exception with a non-datetime expires_at."
            )
