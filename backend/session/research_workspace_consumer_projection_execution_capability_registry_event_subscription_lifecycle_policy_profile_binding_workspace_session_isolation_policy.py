from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_isolation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError,
)

VALID_SESSION_ISOLATION_LEVELS = (
    "STRICT",
    "SHARED",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationPolicy:
    """
    Immutable configuration describing how strictly concurrent
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    sessions are kept from accessing or modifying each other's runtime
    state.

    The policy is a value object only. It performs no enforcement.
    Granting, revoking, and validating resource access are the
    responsibility of a session isolation service.

    Attributes:
        policy_id: The policy's unique identifier
        isolation_level: How strictly resource access is isolated
            between sessions, one of "STRICT" or "SHARED". Under
            "STRICT", a resource outside shared_resources may be
            granted to only one session at a time. Under "SHARED",
            any resource may be granted to any number of sessions
        shared_resources: The resource identifiers every session may
            access without an explicit grant, regardless of
            isolation_level
    """

    policy_id: str

    isolation_level: str

    shared_resources: tuple[str, ...]

    def __post_init__(self):
        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError(
                "Cannot build a session isolation policy with an empty or blank policy ID."
            )

        if (
            self.isolation_level is None
            or not isinstance(self.isolation_level, str)
            or not self.isolation_level.strip()
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError(
                "Cannot build a session isolation policy with an empty, blank, or non-string isolation_level."
            )

        if self.isolation_level not in VALID_SESSION_ISOLATION_LEVELS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError(
                f"Invalid session isolation policy isolation_level {self.isolation_level!r}. Must be one of "
                f"{VALID_SESSION_ISOLATION_LEVELS!r}."
            )

        if self.shared_resources is None or not isinstance(self.shared_resources, tuple):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError(
                "Cannot build a session isolation policy with shared_resources that is not a tuple."
            )

        for resource in self.shared_resources:
            if resource is None or not isinstance(resource, str) or not resource.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError(
                    "Cannot build a session isolation policy with an empty, blank, or non-string shared resource."
                )
