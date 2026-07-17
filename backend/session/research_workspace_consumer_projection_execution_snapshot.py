from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_authorization import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization,
)

from .research_workspace_consumer_projection_execution_decision import (
    ResearchWorkspaceConsumerProjectionExecutionDecision,
)

from .research_workspace_consumer_projection_execution_eligibility import (
    ResearchWorkspaceConsumerProjectionExecutionEligibility,
)

from .research_workspace_consumer_projection_execution_gate_status import (
    ResearchWorkspaceConsumerProjectionExecutionGateStatus,
)

from .research_workspace_consumer_projection_execution_outcome import (
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
)

from .research_workspace_consumer_projection_execution_outcome_reason import (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason,
)

from .research_workspace_consumer_projection_execution_verdict import (
    ResearchWorkspaceConsumerProjectionExecutionVerdict,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionSnapshot:
    """
    Compact, immutable representation of the complete execution
    state for one projection.

    Bundles the eligibility, execution decision, execution gate,
    authorization, verdict, and outcome/summary of the execution
    policy chain into one flat object - the earlier reports remain
    useful for specialized consumers at each policy boundary, while
    this snapshot is the one compact handoff point for a future API,
    dashboard, logging, or persistence layer.

    Carries no execution engine, scheduler, or workflow state - this
    is a canonical execution-state artifact, not an execution result.

    Attributes:
        projection_name: Projection name reused from the input artifacts
        eligibility: Eligibility reused from the eligibility report
        decision: Decision reused from the execution decision report
        gate: Gate status reused from the execution gate report
        authorization: Authorization reused from the authorization report
        verdict: Verdict reused from the execution verdict report
        outcome: Outcome reused from the execution summary
        reason: Reason reused from the execution summary
        title: Title reused from the execution summary
        description: Description reused from the execution summary
        ready_for_execution: Flag reused from the execution summary
    """

    projection_name: str

    eligibility: (
        ResearchWorkspaceConsumerProjectionExecutionEligibility
    )

    decision: (
        ResearchWorkspaceConsumerProjectionExecutionDecision
    )

    gate: (
        ResearchWorkspaceConsumerProjectionExecutionGateStatus
    )

    authorization: (
        ResearchWorkspaceConsumerProjectionExecutionAuthorization
    )

    verdict: (
        ResearchWorkspaceConsumerProjectionExecutionVerdict
    )

    outcome: (
        ResearchWorkspaceConsumerProjectionExecutionOutcome
    )

    reason: (
        ResearchWorkspaceConsumerProjectionExecutionOutcomeReason
    )

    title: str

    description: str

    ready_for_execution: bool

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "eligibility": self.eligibility.value,
            "decision": self.decision.value,
            "gate": self.gate.value,
            "authorization": self.authorization.value,
            "verdict": self.verdict.value,
            "outcome": self.outcome.value,
            "reason": self.reason.value,
            "title": self.title,
            "description": self.description,
            "ready_for_execution": self.ready_for_execution,
        }
