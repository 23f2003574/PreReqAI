from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_resource_governance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourcePolicy:
    """
    Immutable, reusable configuration capping how much CPU, memory,
    and storage a single consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session governed by it may consume.

    The policy is a value object only. It performs no allocation or
    enforcement. Allocating, releasing, and validating resource usage
    against a policy are the responsibility of a session resource
    governance service.

    Attributes:
        policy_id: The policy's unique identifier
        cpu_limit: The maximum CPU a governed session may consume
        memory_limit: The maximum memory a governed session may
            consume
        storage_limit: The maximum storage a governed session may
            consume
    """

    policy_id: str

    cpu_limit: float

    memory_limit: float

    storage_limit: float

    def __post_init__(self):
        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError(
                "Cannot build a session resource policy with an empty or blank policy ID."
            )

        for value, label in (
            (self.cpu_limit, "cpu_limit"),
            (self.memory_limit, "memory_limit"),
            (self.storage_limit, "storage_limit"),
        ):
            if value is None or isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError(
                    f"Invalid session resource policy {label} {value!r}; {label} must be a positive number."
                )
