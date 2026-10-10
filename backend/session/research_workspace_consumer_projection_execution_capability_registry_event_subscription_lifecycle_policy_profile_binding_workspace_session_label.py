from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_label_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabel:
    """
    Immutable key/value tag attached to a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace execution session, so it can be found
    through fast, indexed, exact-match filtering instead of scanning
    every session.

    The label is a value object only. It performs no indexing.
    Adding, removing, and indexing labels are the responsibility of a
    session label service.

    Attributes:
        session_id: The identifier of the execution session this
            label is attached to
        key: The label's name, unique within its session
        value: The label's value, matched exactly by lookups
    """

    session_id: str

    key: str

    value: str

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError(
                "Cannot build a session label with an empty or blank session ID."
            )

        if self.key is None or not self.key.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError(
                "Cannot build a session label with an empty or blank key."
            )

        if self.value is None or not isinstance(self.value, str) or not self.value.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError(
                "Cannot build a session label with an empty, blank, or non-string value."
            )
