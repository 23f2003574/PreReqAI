from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_eligibility import (
    ResearchWorkspaceConsumerProjectionExecutionEligibility,
)

from .research_workspace_consumer_projection_execution_eligibility_reason import (
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReason,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionEligibilityReport:
    """
    The immutable result of evaluating whether a consumer
    projection is eligible for execution, based solely on its
    readiness report.

    Attributes:
        projection_name: Identifies the evaluated projection
        eligibility: The overall execution eligibility classification
        reason: The primary cause of the eligibility classification
        executable: Whether execution can proceed at all, carried
            forward unchanged from the readiness report
    """

    projection_name: str

    eligibility: (
        ResearchWorkspaceConsumerProjectionExecutionEligibility
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionEligibilityReason
    )

    executable: bool

    @property
    def eligible(self) -> bool:
        return (
            self.eligibility
            != ResearchWorkspaceConsumerProjectionExecutionEligibility.INELIGIBLE
        )

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "eligibility": self.eligibility.value,
            "reason": self.reason.value,
            "executable": self.executable,
            "eligible": self.eligible,
        }
