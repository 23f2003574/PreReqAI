from .research_workspace_consumer_projection_derivation_provenance import (
    ResearchWorkspaceConsumerProjectionDerivationProvenance,
)

from .research_workspace_consumer_projection_output_provenance import (
    ResearchWorkspaceConsumerProjectionOutputProvenance,
)

from .research_workspace_consumer_projection_provenance_edge import (
    ResearchWorkspaceConsumerProjectionProvenanceEdge,
)

from .research_workspace_consumer_projection_provenance_report import (
    ResearchWorkspaceConsumerProjectionProvenanceReport,
)

from .research_workspace_consumer_projection_source_provenance import (
    ResearchWorkspaceConsumerProjectionSourceProvenance,
)


class ResearchWorkspaceConsumerProjectionProvenanceCollector:
    """
    Mutable, operation-scoped collector
    of evidence lineage. Produces one
    immutable, acyclic provenance report
    when built.

    Source nodes are deduplicated by
    source_name — one request-scoped
    resolution always maps to one source
    node, matching Commit #6's shared
    resolution model. Output nodes are
    deduplicated by (output_type,
    output_key) but reject a second
    registration of the same identity,
    since two logically different
    results should never share one key.
    """

    def __init__(

        self,

        *,

        operation_name,

    ):

        self._operation_name = (
            operation_name
        )

        self._finalized = False

        self._final_report = None

        self._sequence = 0

        self._sources = []

        self._derivations = []

        self._outputs = []

        self._edges = []

        self._all_node_ids = set()

        self._edge_pairs = set()

        self._forward_adjacency = {}

        self._source_node_ids_by_name = (
            {}
        )

        self._output_node_ids_by_key = (
            {}
        )

    def _ensure_open(self):

        if self._finalized:

            raise RuntimeError(
                "Cannot record provenance "
                "after the collector has "
                "been finalized"
            )

    def _next_node_id(

        self,

        prefix,

    ):

        self._sequence += 1

        return (
            f"{prefix}:{self._sequence}"
        )

    def register_source(

        self,

        *,

        source_name,

        source_timestamp=None,

        freshness_status=None,

    ):

        self._ensure_open()

        if (

            source_name

            in self._source_node_ids_by_name
        ):

            return (

                self._source_node_ids_by_name[
                    source_name
                ]
            )

        node_id = (

            self._next_node_id(
                "source"
            )
        )

        self._sources.append(

            ResearchWorkspaceConsumerProjectionSourceProvenance(

                node_id=node_id,

                source_name=(
                    source_name
                ),

                source_timestamp=(
                    source_timestamp
                ),

                freshness_status=(
                    freshness_status
                ),
            )
        )

        self._source_node_ids_by_name[
            source_name
        ] = node_id

        self._all_node_ids.add(
            node_id
        )

        return node_id

    def register_derivation(

        self,

        *,

        rule_name,

    ):

        self._ensure_open()

        node_id = (

            self._next_node_id(
                "derivation"
            )
        )

        self._derivations.append(

            ResearchWorkspaceConsumerProjectionDerivationProvenance(

                node_id=node_id,

                rule_name=rule_name,
            )
        )

        self._all_node_ids.add(
            node_id
        )

        return node_id

    def register_output(

        self,

        *,

        output_type,

        output_key,

    ):

        self._ensure_open()

        key = (

            output_type,

            output_key,
        )

        if (

            key

            in self._output_node_ids_by_key
        ):

            raise ValueError(

                "Duplicate provenance "
                f"output registration: "
                f"{output_type}:{output_key}"
            )

        node_id = (

            self._next_node_id(
                "output"
            )
        )

        self._outputs.append(

            ResearchWorkspaceConsumerProjectionOutputProvenance(

                node_id=node_id,

                output_type=(
                    output_type
                ),

                output_key=(
                    output_key
                ),
            )
        )

        self._output_node_ids_by_key[
            key
        ] = node_id

        self._all_node_ids.add(
            node_id
        )

        return node_id

    def get_output_node_id(

        self,

        *,

        output_type,

        output_key,

    ):

        return (

            self._output_node_ids_by_key
            .get(

                (
                    output_type,

                    output_key,
                )
            )
        )

    def _can_reach(

        self,

        start,

        target,

    ):

        visited = set()

        stack = [
            start
        ]

        while stack:

            current = stack.pop()

            if current == target:

                return True

            if current in visited:

                continue

            visited.add(
                current
            )

            stack.extend(

                self._forward_adjacency
                .get(

                    current,

                    (),
                )
            )

        return False

    def add_edge(

        self,

        *,

        from_node_id,

        to_node_id,

    ):

        self._ensure_open()

        if from_node_id == to_node_id:

            raise ValueError(

                "Provenance edge cannot "
                "connect a node to itself: "
                f"{from_node_id}"
            )

        if (

            from_node_id

            not in self._all_node_ids
        ):

            raise ValueError(

                "Unknown provenance "
                f"node: {from_node_id}"
            )

        if (

            to_node_id

            not in self._all_node_ids
        ):

            raise ValueError(

                "Unknown provenance "
                f"node: {to_node_id}"
            )

        pair = (

            from_node_id,

            to_node_id,
        )

        if pair in self._edge_pairs:

            return None

        if self._can_reach(

            to_node_id,

            from_node_id,
        ):

            raise ValueError(

                "Adding provenance edge "
                f"{from_node_id} -> "
                f"{to_node_id} would "
                "create a cycle"
            )

        self._edge_pairs.add(
            pair
        )

        self._edges.append(

            ResearchWorkspaceConsumerProjectionProvenanceEdge(

                from_node_id=(
                    from_node_id
                ),

                to_node_id=(
                    to_node_id
                ),
            )
        )

        self._forward_adjacency.setdefault(

            from_node_id,

            set(),

        ).add(
            to_node_id
        )

        return None

    def record_derivation(

        self,

        *,

        rule_name,

        input_node_ids,

        output_type,

        output_key,

    ):

        self._ensure_open()

        derivation_node_id = (

            self.register_derivation(
                rule_name=rule_name,
            )
        )

        for input_node_id in (
            input_node_ids
        ):

            self.add_edge(

                from_node_id=(
                    input_node_id
                ),

                to_node_id=(
                    derivation_node_id
                ),
            )

        output_node_id = (

            self.register_output(

                output_type=(
                    output_type
                ),

                output_key=(
                    output_key
                ),
            )
        )

        self.add_edge(

            from_node_id=(
                derivation_node_id
            ),

            to_node_id=(
                output_node_id
            ),
        )

        return output_node_id

    def build_report(self):

        if self._finalized:

            return self._final_report

        self._finalized = True

        self._final_report = (

            ResearchWorkspaceConsumerProjectionProvenanceReport(

                operation_name=(
                    self._operation_name
                ),

                sources=list(
                    self._sources
                ),

                derivations=list(
                    self._derivations
                ),

                outputs=list(
                    self._outputs
                ),

                edges=list(
                    self._edges
                ),
            )
        )

        return self._final_report
