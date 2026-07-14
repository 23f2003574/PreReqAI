from .research_workspace_consumer_projection_budget_admission import (
    ResearchWorkspaceConsumerProjectionBudgetAdmission,
)

from .research_workspace_consumer_projection_budget_decision import (
    ResearchWorkspaceConsumerProjectionBudgetDecision,
)

from .research_workspace_consumer_projection_budget_snapshot import (
    ResearchWorkspaceConsumerProjectionBudgetSnapshot,
)

from .research_workspace_consumer_projection_budget_summary import (
    ResearchWorkspaceConsumerProjectionBudgetSummary,
)

from .research_workspace_consumer_projection_diagnostic_report import (
    ResearchWorkspaceConsumerProjectionDiagnosticReport,
)


class ResearchWorkspaceConsumerProjectionBudgetSummarySummarizer:
    """
    Derives compact budget summary from finalized budget state.

    This pure summarizer is used by both the receipt builder and the
    receipt verifier to ensure consistent summary derivation from the
    same finalized artifacts.

    Does not reinterpret budget decisions or infer skips from missing
    projection sections. Summarizes only explicit budget decisions.
    """

    def summarize(
        self,
        *,
        budget_snapshot: (
            ResearchWorkspaceConsumerProjectionBudgetSnapshot
        ),
        diagnostic_report: (
            ResearchWorkspaceConsumerProjectionDiagnosticReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionBudgetSummary:
        """
        Derive a compact summary from the finalized budget state.

        Args:
            budget_snapshot: The finalized budget snapshot
            diagnostic_report: The finalized diagnostic report with budget decisions

        Returns:
            Compact summary of budget behavior
        """

        budgeted = budget_snapshot.soft_budget_ms is not None

        admitted_stage_count = 0
        skipped_stage_count = 0

        for admission in diagnostic_report.budget_decisions:
            if admission.decision == ResearchWorkspaceConsumerProjectionBudgetDecision.EXECUTE:
                admitted_stage_count += 1
            elif admission.decision == ResearchWorkspaceConsumerProjectionBudgetDecision.SKIP:
                skipped_stage_count += 1

        return ResearchWorkspaceConsumerProjectionBudgetSummary(
            budgeted=budgeted,
            admitted_stage_count=admitted_stage_count,
            skipped_stage_count=skipped_stage_count,
            exhausted=budget_snapshot.exhausted,
        )
