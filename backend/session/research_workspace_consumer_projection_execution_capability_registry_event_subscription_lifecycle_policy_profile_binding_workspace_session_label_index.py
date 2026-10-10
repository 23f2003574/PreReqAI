from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_label_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelIndex:
    """
    Immutable, point-in-time snapshot of every session currently
    carrying a given label key, within a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace.

    The index is a value object only. It performs no lookup or
    maintenance. Building and maintaining the index are the
    responsibility of a session label service.

    Attributes:
        label_key: The label key this index entry concerns
        session_ids: Every session currently carrying label_key, in
            no particular order
    """

    label_key: str

    session_ids: tuple[str, ...]

    def __post_init__(self):
        if self.label_key is None or not self.label_key.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError(
                "Cannot build a session label index with an empty or blank label key."
            )

        if self.session_ids is None or not isinstance(self.session_ids, tuple):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError(
                "Cannot build a session label index with session_ids that is not a tuple."
            )

        for session_id in self.session_ids:
            if session_id is None or not isinstance(session_id, str) or not session_id.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError(
                    "Cannot build a session label index with an empty, blank, or non-string session ID."
                )
