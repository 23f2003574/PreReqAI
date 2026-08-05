from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_lifecycle_hook_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHookResult:
    """
    Immutable outcome of running a single consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace session lifecycle hook.

    The result is a value object only. It performs no execution.
    Executing hooks is the responsibility of a session lifecycle hook
    service.

    Attributes:
        hook_id: The identifier of the hook this result concerns
        executed: Whether the hook's handler ran to completion without
            raising
        duration_ms: How long the hook's handler took to run, in
            milliseconds
    """

    hook_id: str

    executed: bool

    duration_ms: float

    def __post_init__(self):
        if self.hook_id is None or not self.hook_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError(
                "Cannot build a session hook result with an empty or blank hook ID."
            )

        if self.executed is None or not isinstance(self.executed, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError(
                "Cannot build a session hook result with a non-boolean executed."
            )

        if (
            self.duration_ms is None
            or isinstance(self.duration_ms, bool)
            or not isinstance(self.duration_ms, (int, float))
            or self.duration_ms < 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError(
                "Cannot build a session hook result with a negative or non-numeric duration_ms."
            )
