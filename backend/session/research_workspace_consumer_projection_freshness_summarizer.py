from .research_workspace_consumer_projection_diagnostic_report import (
    ResearchWorkspaceConsumerProjectionDiagnosticReport,
)

from .research_workspace_consumer_projection_freshness_status import (
    ResearchWorkspaceConsumerProjectionFreshnessStatus,
)

from .research_workspace_consumer_projection_freshness_summary import (
    ResearchWorkspaceConsumerProjectionFreshnessSummary,
)


class ResearchWorkspaceConsumerProjectionFreshnessSummarizer:
    """
    Derives compact freshness summary from finalized diagnostic report.

    This pure summarizer is used by both the receipt builder and the
    receipt verifier to ensure consistent summary derivation from the
    same finalized artifacts.

    Does not recompute freshness or call the clock.
    Simply summarizes the existing freshness classifications.
    """

    def summarize(
        self,
        report: (
            ResearchWorkspaceConsumerProjectionDiagnosticReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionFreshnessSummary:
        """
        Derive a compact summary from the finalized freshness classifications.

        Args:
            report: The finalized diagnostic report containing freshness evaluations

        Returns:
            Compact summary of source freshness classifications
        """

        observed_source_count = 0
        fresh_source_count = 0
        stale_usable_source_count = 0
        expired_source_count = 0
        unknown_source_count = 0

        for input_diagnostic in report.inputs:
            if input_diagnostic.freshness is not None:
                observed_source_count += 1

                status = input_diagnostic.freshness.status

                if status == ResearchWorkspaceConsumerProjectionFreshnessStatus.FRESH:
                    fresh_source_count += 1

                elif status == ResearchWorkspaceConsumerProjectionFreshnessStatus.STALE:
                    stale_usable_source_count += 1

                elif (
                    status
                    == ResearchWorkspaceConsumerProjectionFreshnessStatus.UNUSABLE
                ):
                    expired_source_count += 1
            else:
                # Input without freshness evaluation
                unknown_source_count += 1

        return ResearchWorkspaceConsumerProjectionFreshnessSummary(
            observed_source_count=observed_source_count,
            fresh_source_count=fresh_source_count,
            stale_usable_source_count=stale_usable_source_count,
            expired_source_count=expired_source_count,
            unknown_source_count=unknown_source_count,
        )
