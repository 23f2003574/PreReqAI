from datetime import (
    datetime,
)

from .research_workspace_consumer_projection_budget_snapshot import (
    ResearchWorkspaceConsumerProjectionBudgetSnapshot,
)

from .research_workspace_consumer_projection_budget_summarizer import (
    ResearchWorkspaceConsumerProjectionBudgetSummarySummarizer,
)

from .research_workspace_consumer_projection_diagnostic_report import (
    ResearchWorkspaceConsumerProjectionDiagnosticReport,
)

from .research_workspace_consumer_projection_diagnostics_summarizer import (
    ResearchWorkspaceConsumerProjectionDiagnosticsSummarizer,
)

from .research_workspace_consumer_projection_execution_outcome_resolver import (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver,
)

from .research_workspace_consumer_projection_execution_receipt import (
    ResearchWorkspaceConsumerProjectionExecutionReceipt,
)

from .research_workspace_consumer_projection_fingerprint_snapshot import (
    ResearchWorkspaceConsumerProjectionFingerprintSnapshot,
)

from .research_workspace_consumer_projection_freshness_summarizer import (
    ResearchWorkspaceConsumerProjectionFreshnessSummarizer,
)

from .research_workspace_consumer_projection_identity import (
    ResearchWorkspaceConsumerProjectionIdentity,
)

from .research_workspace_consumer_projection_provenance_report import (
    ResearchWorkspaceConsumerProjectionProvenanceReport,
)

from .research_workspace_consumer_projection_provenance_summarizer import (
    ResearchWorkspaceConsumerProjectionProvenanceSummarizer,
)


class ResearchWorkspaceConsumerProjectionExecutionReceiptBuilder:
    """
    Builds immutable execution receipts from finalized execution artifacts.

    The receipt builder:
    - Consumes finalized execution artifacts
    - Derives compact summaries using pure summarizers
    - Resolves execution outcome using the outcome resolver
    - Builds an immutable receipt

    The builder does NOT:
    - Resolve data or call repositories
    - Recompute the projection fingerprint
    - Recompute freshness classifications
    - Recompute provenance
    - Reinterpret budget decisions
    - Read the clock (reuses existing observation time)

    The builder is stateless - equivalent inputs produce equivalent outputs.
    """

    def __init__(
        self,
        *,
        diagnostics_summarizer: (
            ResearchWorkspaceConsumerProjectionDiagnosticsSummarizer
        ) = None,
        freshness_summarizer: (
            ResearchWorkspaceConsumerProjectionFreshnessSummarizer
        ) = None,
        budget_summarizer: (
            ResearchWorkspaceConsumerProjectionBudgetSummarySummarizer
        ) = None,
        provenance_summarizer: (
            ResearchWorkspaceConsumerProjectionProvenanceSummarizer
        ) = None,
        outcome_resolver: (
            ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver
        ) = None,
    ):

        self._diagnostics_summarizer = (
            diagnostics_summarizer
            or ResearchWorkspaceConsumerProjectionDiagnosticsSummarizer()
        )

        self._freshness_summarizer = (
            freshness_summarizer
            or ResearchWorkspaceConsumerProjectionFreshnessSummarizer()
        )

        self._budget_summarizer = (
            budget_summarizer
            or ResearchWorkspaceConsumerProjectionBudgetSummarySummarizer()
        )

        self._provenance_summarizer = (
            provenance_summarizer
            or ResearchWorkspaceConsumerProjectionProvenanceSummarizer()
        )

        self._outcome_resolver = (
            outcome_resolver
            or ResearchWorkspaceConsumerProjectionExecutionOutcomeResolver()
        )

    def build(
        self,
        *,
        execution_id: str,
        observed_at: datetime,
        projection_name: str,
        contract_version: str = None,
        fingerprint_snapshot: (
            ResearchWorkspaceConsumerProjectionFingerprintSnapshot
        ) = None,
        diagnostic_report: (
            ResearchWorkspaceConsumerProjectionDiagnosticReport
        ) = None,
        provenance_report: (
            ResearchWorkspaceConsumerProjectionProvenanceReport
        ) = None,
        budget_snapshot: (
            ResearchWorkspaceConsumerProjectionBudgetSnapshot
        ) = None,
    ) -> ResearchWorkspaceConsumerProjectionExecutionReceipt:
        """
        Build an immutable execution receipt from finalized artifacts.

        Args:
            execution_id: Stable execution identifier from request scope
            observed_at: Request-scoped observation time (reused from context)
            projection_name: Name of the projection that was executed
            contract_version: Optional contract version active at execution time
            fingerprint_snapshot: Finalized fingerprint snapshot from Commit #12
            diagnostic_report: Finalized diagnostic report from Commit #8
            provenance_report: Finalized provenance report from Commit #11
            budget_snapshot: Finalized budget snapshot from Commit #9

        Returns:
            Immutable execution receipt summarizing the completed execution
        """

        # Derive summaries from finalized artifacts
        diagnostics_summary = self._diagnostics_summarizer.summarize(
            report=diagnostic_report,
        )

        freshness_summary = self._freshness_summarizer.summarize(
            report=diagnostic_report,
        )

        budget_summary = self._budget_summarizer.summarize(
            budget_snapshot=budget_snapshot,
            diagnostic_report=diagnostic_report,
        )

        provenance_summary = self._provenance_summarizer.summarize(
            report=provenance_report,
        )

        # Resolve execution outcome from summaries
        status = self._outcome_resolver.resolve(
            diagnostics=diagnostics_summary,
            freshness=freshness_summary,
            budget=budget_summary,
            provenance=provenance_summary,
        )

        # Build projection identity
        identity = ResearchWorkspaceConsumerProjectionIdentity(
            projection_name=projection_name,
            contract_version=contract_version,
            fingerprint=(
                fingerprint_snapshot.overall
                if fingerprint_snapshot
                else None
            ),
        )

        # Build and return immutable receipt
        return ResearchWorkspaceConsumerProjectionExecutionReceipt(
            execution_id=execution_id,
            observed_at=observed_at,
            identity=identity,
            status=status,
            diagnostics=diagnostics_summary,
            freshness=freshness_summary,
            budget=budget_summary,
            provenance=provenance_summary,
        )
