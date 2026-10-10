from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionProvenanceSummary:
    """
    Compact summary of provenance coverage.

    Summarizes the provenance graph structure and coverage
    without duplicating the full graph. The important concept
    is provenance coverage - whether every consumer-facing
    output has provenance.

    Attributes:
        source_node_count: Number of source nodes in provenance graph
        derivation_node_count: Number of derivation nodes in provenance graph
        output_node_count: Number of output nodes in provenance graph
        edge_count: Number of edges in provenance graph
        covered_output_count: Number of outputs with provenance
        uncovered_output_count: Number of outputs without provenance
    """

    source_node_count: int

    derivation_node_count: int

    output_node_count: int

    edge_count: int

    covered_output_count: int

    uncovered_output_count: int
