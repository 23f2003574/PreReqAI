from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_authorization import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization,
)

from .research_workspace_consumer_projection_execution_authorization_reason import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionAuthorizationReport:
    """
    The immutable result of resolving a consumer projection's
    execution gate status into a policy authorization result.

    Attributes:
        projection_name: Identifies the evaluated projection
        authorization: The resolved execution authorization
        reason: The primary cause of the authorization result
        authorized: Whether execution is authorized right now
    """

    projection_name: str

    authorization: (
        ResearchWorkspaceConsumerProjectionExecutionAuthorization
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason
    )

    authorized: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "authorization": self.authorization.value,
            "reason": self.reason.value,
            "authorized": self.authorized,
        }
