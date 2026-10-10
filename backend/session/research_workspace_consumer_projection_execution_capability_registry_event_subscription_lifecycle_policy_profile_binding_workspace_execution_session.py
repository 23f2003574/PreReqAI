from dataclasses import (
    dataclass,
    field,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSession:
    """
    Immutable, point-in-time view of a single consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace execution session: the runtime
    state, ownership, and lifecycle of one isolated pipeline run,
    kept independent of the pipeline's own definition.

    The session is a value object only. It performs no lifecycle
    transitions. Starting, finishing, and cancelling a session are
    the responsibility of an execution session service.

    Attributes:
        session_id: The session's unique identifier
        pipeline_id: The identifier of the pipeline this session is
            running
        status: The session's current lifecycle state
        owner: The identifier of whoever started this session
        started_at: When this session began
        finished_at: When this session finished or was cancelled, or
            None while it is still active
    """

    session_id: str

    pipeline_id: str

    status: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus

    owner: str

    started_at: datetime

    finished_at: datetime = field(default=None)

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                "Cannot build an execution session with an empty or blank session ID."
            )

        if self.pipeline_id is None or not self.pipeline_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                "Cannot build an execution session with an empty or blank pipeline ID."
            )

        if not isinstance(self.status, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                "Cannot build an execution session: status must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus."
            )

        if self.owner is None or not self.owner.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                "Cannot build an execution session with an empty or blank owner."
            )

        if self.started_at is None or not isinstance(self.started_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                "Cannot build an execution session with a non-datetime started_at."
            )

        if self.finished_at is not None and not isinstance(self.finished_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                "Cannot build an execution session with a non-datetime finished_at."
            )
