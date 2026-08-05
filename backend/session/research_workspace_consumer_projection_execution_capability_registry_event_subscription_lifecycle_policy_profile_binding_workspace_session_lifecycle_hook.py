from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_lifecycle_hook_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError,
)

VALID_SESSION_LIFECYCLE_HOOK_EVENTS = (
    "START",
    "FINISH",
    "CANCEL",
    "RESTORE",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHook:
    """
    Immutable registration of custom logic to run at a specific
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    session lifecycle event, so callers can extend session behavior
    without modifying the session engine itself.

    The hook is a value object only. It performs no execution.
    Registering, enabling, disabling, and executing hooks are the
    responsibility of a session lifecycle hook service.

    Attributes:
        hook_id: The hook's unique identifier
        event: The lifecycle event this hook runs on, one of "START",
            "FINISH", "CANCEL", or "RESTORE"
        handler: The callable invoked with a session ID when this
            hook runs
        enabled: Whether this hook currently runs when its event
            fires
    """

    hook_id: str

    event: str

    handler: object

    enabled: bool

    def __post_init__(self):
        if self.hook_id is None or not self.hook_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError(
                "Cannot build a session lifecycle hook with an empty or blank hook ID."
            )

        if self.event is None or not isinstance(self.event, str) or not self.event.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError(
                "Cannot build a session lifecycle hook with an empty, blank, or non-string event."
            )

        if self.event not in VALID_SESSION_LIFECYCLE_HOOK_EVENTS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError(
                f"Invalid session lifecycle hook event {self.event!r}. Must be one of "
                f"{VALID_SESSION_LIFECYCLE_HOOK_EVENTS!r}."
            )

        if not callable(self.handler):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError(
                "Cannot build a session lifecycle hook with a non-callable handler."
            )

        if self.enabled is None or not isinstance(self.enabled, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError(
                "Cannot build a session lifecycle hook with a non-boolean enabled."
            )
