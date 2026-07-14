from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_consumer_projection_derivation_provenance import (
    ResearchWorkspaceConsumerProjectionDerivationProvenance,
)

from .research_workspace_consumer_projection_output_provenance import (
    ResearchWorkspaceConsumerProjectionOutputProvenance,
)

from .research_workspace_consumer_projection_provenance_edge import (
    ResearchWorkspaceConsumerProjectionProvenanceEdge,
)

from .research_workspace_consumer_projection_source_provenance import (
    ResearchWorkspaceConsumerProjectionSourceProvenance,
)


@dataclass
class ResearchWorkspaceConsumerProjectionProvenanceReport:
    """
    The immutable, finalized evidence
    lineage graph for one logical
    consumer projection operation.
    Read-only traversal only — the
    report never mutates itself.
    """

    operation_name: str

    sources: list[
        ResearchWorkspaceConsumerProjectionSourceProvenance
    ] = field(
        default_factory=list,
    )

    derivations: list[
        ResearchWorkspaceConsumerProjectionDerivationProvenance
    ] = field(
        default_factory=list,
    )

    outputs: list[
        ResearchWorkspaceConsumerProjectionOutputProvenance
    ] = field(
        default_factory=list,
    )

    edges: list[
        ResearchWorkspaceConsumerProjectionProvenanceEdge
    ] = field(
        default_factory=list,
    )

    def _reverse_adjacency(self):

        adjacency = {}

        for edge in self.edges:

            adjacency.setdefault(

                edge.to_node_id,

                set(),

            ).add(
                edge.from_node_id
            )

        return adjacency

    def _forward_adjacency(self):

        adjacency = {}

        for edge in self.edges:

            adjacency.setdefault(

                edge.from_node_id,

                set(),

            ).add(
                edge.to_node_id
            )

        return adjacency

    def get_ancestors(

        self,

        node_id,

    ):

        reverse = (
            self._reverse_adjacency()
        )

        visited = set()

        stack = list(

            reverse.get(
                node_id,

                (),
            )
        )

        while stack:

            current = stack.pop()

            if current in visited:

                continue

            visited.add(
                current
            )

            stack.extend(

                reverse.get(
                    current,

                    (),
                )
            )

        return visited

    def get_source_ancestors(

        self,

        node_id,

    ):

        ancestor_ids = (

            self.get_ancestors(
                node_id
            )
        )

        return [

            source

            for source

            in self.sources

            if (

                source.node_id

                in ancestor_ids
            )
        ]

    def get_output_descendants(

        self,

        node_id,

    ):

        forward = (
            self._forward_adjacency()
        )

        visited = set()

        stack = list(

            forward.get(
                node_id,

                (),
            )
        )

        while stack:

            current = stack.pop()

            if current in visited:

                continue

            visited.add(
                current
            )

            stack.extend(

                forward.get(
                    current,

                    (),
                )
            )

        return [

            output

            for output

            in self.outputs

            if (

                output.node_id

                in visited
            )
        ]

    def to_dict(self):

        return {

            "operation_name":
                self.operation_name,

            "sources": [

                source.to_dict()

                for source

                in self.sources
            ],

            "derivations": [

                derivation.to_dict()

                for derivation

                in self.derivations
            ],

            "outputs": [

                output.to_dict()

                for output

                in self.outputs
            ],

            "edges": [

                edge.to_dict()

                for edge

                in self.edges
            ],
        }
