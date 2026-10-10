from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_variable_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariable:
    """
    Immutable, point-in-time view of a single key/value entry in a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    session's local variable store.

    The variable is a value object only. It performs no storage.
    Storing, retrieving, and removing variables are the
    responsibility of a session variable service.

    Attributes:
        session_id: The identifier of the execution session this
            variable belongs to
        key: The variable's name, unique within its session
        value: The variable's current value
        updated_at: When this key was last written
    """

    session_id: str

    key: str

    value: object

    updated_at: datetime

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError(
                "Cannot build a session variable with an empty or blank session ID."
            )

        if self.key is None or not self.key.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError(
                "Cannot build a session variable with an empty or blank key."
            )

        if self.updated_at is None or not isinstance(self.updated_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError(
                "Cannot build a session variable with a non-datetime updated_at."
            )
