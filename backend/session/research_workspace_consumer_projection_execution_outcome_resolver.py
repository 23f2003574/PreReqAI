from .research_workspace_consumer_projection_budget_summary import (
    ResearchWorkspaceConsumerProjectionBudgetSummary,
)

from .research_workspace_consumer_projection_diagnostics_summary import (
    ResearchWorkspaceConsumerProjectionDiagnosticsSummary,
)

from .research_workspace_consumer_projection_execution_status import (
    ResearchWorkspaceConsumerProjectionExecutionStatus,
)

from .research_workspace_consumer_projection_freshness_summary import (
    ResearchWorkspaceConsumerProjectionFreshnessSummary,
)

from .research_workspace_consumer_projection_provenance_summary import (
    ResearchWorkspaceConsumerProjectionProvenanceSummary,
)


class ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver:
    """
    Resolves the overall execution outcome (SUCCEEDED or DEGRADED).

    This centralized logic ensures deterministic outcome resolution
    from the finalized execution summaries. Both the receipt builder
    and the receipt verifier use this resolver to ensure consistent
    outcome determination.

    The resolver follows existing execution semantics rather than
    inventing hidden degradation rules. It derives degradation from:
    - Explicitly degraded diagnostic stages
    - Stale-but-usable sources (when policy marks that as degradation)
    - Optional work skipped due to budget pressure
    - Fallback sources (if tracked as degradation)
    - Missing required provenance coverage (if provenance is a guarantee)

    Does not automatically treat every unusual condition as degraded.
    Follows the existing architecture's degradation semantics.
    """

    def resolve(
        self,
        *,
        diagnostics: (
            ResearchWorkspaceConsumerProjectionDiagnosticsSummary
        ),
        freshness: (
            ResearchWorkspaceConsumerProjectionFreshnessSummary
        ),
        budget: (
            ResearchWorkspaceConsumerProjectionBudgetSummary
        ),
        provenance: (
            ResearchWorkspaceConsumerProjectionProvenanceSummary
        ),
    ) -> ResearchWorkspaceConsumerProjectionExecutionStatus:
        """
        Resolve the execution outcome from finalized summaries.

        Args:
            diagnostics: Summary of execution diagnostics
            freshness: Summary of source freshness classifications
            budget: Summary of budget behavior
            provenance: Summary of provenance coverage

        Returns:
            SUCCEEDED if no consumer-relevant degradation detected
            DEGRADED if one or more degradation conditions are present
        """

        # Check for explicitly degraded stages
        if diagnostics.degraded_stage_count > 0:
            return (
                ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED
            )

        # Check for stale-but-usable sources
        # In the current architecture, STALE sources are considered degraded
        # because they represent reduced freshness quality
        if freshness.stale_usable_source_count > 0:
            return (
                ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED
            )

        # Check for expired sources (UNUSABLE status)
        # These represent sources that failed freshness policy
        if freshness.expired_source_count > 0:
            return (
                ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED
            )

        # Check for budget-induced skips
        # Optional stages skipped due to budget pressure indicate degradation
        if budget.budgeted and budget.skipped_stage_count > 0:
            return (
                ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED
            )

        # Check for budget exhaustion
        # Exhausted budget indicates execution under pressure
        if budget.exhausted:
            return (
                ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED
            )

        # Check for missing provenance coverage
        # In the current architecture, missing provenance on outputs
        # indicates reduced execution quality
        if provenance.uncovered_output_count > 0:
            return (
                ResearchWorkspaceConsumerProjectionExecutionStatus.DEGRADED
            )

        # No degradation conditions detected
        return (
            ResearchWorkspaceConsumerProjectionExecutionStatus.SUCCEEDED
        )
