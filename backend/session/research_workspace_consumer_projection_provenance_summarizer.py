from .research_workspace_consumer_projection_provenance_report import (
    ResearchWorkspaceConsumerProjectionProvenanceReport,
)

from .research_workspace_consumer_projection_provenance_summary import (
    ResearchWorkspaceConsumerProjectionProvenanceSummary,
)


class ResearchWorkspaceConsumerProjectionProvenanceSummarizer:
    """
    Derives compact provenance summary from finalized provenance report.

    This pure summarizer is used by both the receipt builder and the
    receipt verifier to ensure consistent summary derivation from the
    same finalized artifacts.

    Does not rebuild derivation lineage or recompute provenance.
    Simply summarizes the existing provenance graph structure and coverage.
    """

    def summarize(
        self,
        report: (
            ResearchWorkspaceConsumerProjectionProvenanceReport
        ),
    ) -> ResearchWorkspaceConsumerProjectionProvenanceSummary:
        """
        Derive a compact summary from the finalized provenance report.

        Args:
            report: The finalized provenance report

        Returns:
            Compact summary of provenance coverage
        """

        source_node_count = len(report.sources)
        derivation_node_count = len(report.derivations)
        output_node_count = len(report.outputs)
        edge_count = len(report.edges)

        # Count covered outputs (outputs that have at least one incoming edge)
        output_node_ids = {output.node_id for output in report.outputs}
        target_node_ids = {edge.to_node_id for edge in report.edges}

        covered_output_count = len(
            output_node_ids.intersection(target_node_ids)
        )
        uncovered_output_count = output_node_count - covered_output_count

        return ResearchWorkspaceConsumerProjectionProvenanceSummary(
            source_node_count=source_node_count,
            derivation_node_count=derivation_node_count,
            output_node_count=output_node_count,
            edge_count=edge_count,
            covered_output_count=covered_output_count,
            uncovered_output_count=uncovered_output_count,
        )
