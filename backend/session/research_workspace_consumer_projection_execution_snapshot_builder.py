from .research_workspace_consumer_projection_execution_authorization_report import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReport,
)

from .research_workspace_consumer_projection_execution_decision_report import (
    ResearchWorkspaceConsumerProjectionExecutionDecisionReport,
)

from .research_workspace_consumer_projection_execution_eligibility_report import (
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReport,
)

from .research_workspace_consumer_projection_execution_gate_report import (
    ResearchWorkspaceConsumerProjectionExecutionGateReport,
)

from .research_workspace_consumer_projection_execution_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionSnapshot,
)

from .research_workspace_consumer_projection_execution_snapshot_error import (
    ResearchWorkspaceConsumerProjectionExecutionSnapshotError,
)

from .research_workspace_consumer_projection_execution_summary import (
    ResearchWorkspaceConsumerProjectionExecutionSummary,
)

from .research_workspace_consumer_projection_execution_verdict_report import (
    ResearchWorkspaceConsumerProjectionExecutionVerdictReport,
)


class ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder:
    """
    Validates and composes an existing eligibility, execution
    decision, execution gate, authorization, verdict, and execution
    summary into one immutable execution snapshot.

    The builder's responsibility is validation and composition, not
    recalculation or repair. It does NOT re-run any policy
    resolution, recalculate the outcome, title, or description,
    access repositories, or read the clock.

    The builder is:
    - Stateless: No instance state
    - Deterministic: Same inputs always produce the same snapshot
    - Side-effect free: Never mutates any input artifact
    """

    def build(
        self,
        eligibility: ResearchWorkspaceConsumerProjectionExecutionEligibilityReport,
        decision: ResearchWorkspaceConsumerProjectionExecutionDecisionReport,
        gate: ResearchWorkspaceConsumerProjectionExecutionGateReport,
        authorization: ResearchWorkspaceConsumerProjectionExecutionAuthorizationReport,
        verdict: ResearchWorkspaceConsumerProjectionExecutionVerdictReport,
        summary: ResearchWorkspaceConsumerProjectionExecutionSummary,
    ) -> ResearchWorkspaceConsumerProjectionExecutionSnapshot:
        """
        Build an execution snapshot from the finalized execution
        policy chain.

        Args:
            eligibility: The eligibility report for this projection
            decision: The execution decision report for this projection
            gate: The execution gate report for this projection
            authorization: The authorization report for this projection
            verdict: The execution verdict report for this projection
            summary: The execution summary for this projection

        Returns:
            An immutable execution snapshot

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionSnapshotError:
                If the artifacts do not all describe the same
                projection
        """

        self._validate_identity(
            eligibility=eligibility,
            decision=decision,
            gate=gate,
            authorization=authorization,
            verdict=verdict,
            summary=summary,
        )

        return ResearchWorkspaceConsumerProjectionExecutionSnapshot(
            projection_name=eligibility.projection_name,
            eligibility=eligibility.eligibility,
            decision=decision.decision,
            gate=gate.status,
            authorization=authorization.authorization,
            verdict=verdict.verdict,
            outcome=summary.outcome,
            reason=summary.reason,
            title=summary.title,
            description=summary.description,
            ready_for_execution=summary.ready_for_execution,
        )

    def _validate_identity(
        self, *, eligibility, decision, gate, authorization, verdict, summary
    ):
        for name, artifact in (
            ("execution decision", decision),
            ("execution gate", gate),
            ("authorization", authorization),
            ("verdict", verdict),
            ("summary", summary),
        ):
            if artifact.projection_name != eligibility.projection_name:
                raise ResearchWorkspaceConsumerProjectionExecutionSnapshotError(
                    f"Cannot build an execution snapshot: {name} "
                    f"projection name '{artifact.projection_name}' does "
                    f"not match eligibility projection name "
                    f"'{eligibility.projection_name}'"
                )
