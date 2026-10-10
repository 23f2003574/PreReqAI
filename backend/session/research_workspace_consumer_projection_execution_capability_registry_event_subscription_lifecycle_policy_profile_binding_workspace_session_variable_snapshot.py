from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_variable_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableSnapshot:
    """
    Immutable, point-in-time copy of every key/value pair held in a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    session's local variable store, taken so it can later be restored.

    The snapshot is a value object only. It performs no storage.
    Taking and restoring snapshots are the responsibility of a
    session variable service.

    Attributes:
        session_id: The identifier of the execution session this
            snapshot was taken from
        variables: The session's variables at the moment this
            snapshot was taken, as a key/value mapping
    """

    session_id: str

    variables: Mapping

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError(
                "Cannot build a session variable snapshot with an empty or blank session ID."
            )

        if self.variables is None or not isinstance(self.variables, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError(
                "Cannot build a session variable snapshot with variables that is not a mapping."
            )
