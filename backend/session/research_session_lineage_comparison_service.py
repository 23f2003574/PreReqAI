from .research_session_collection_difference import (
    ResearchSessionCollectionDifference,
)

from .research_session_divergence import (
    ResearchSessionDivergence,
)

from .research_session_lineage_comparison import (
    ResearchSessionLineageComparison,
)

from .research_session_relationship import (
    ResearchSessionRelationship,
)

from .research_session_state_difference import (
    ResearchSessionStateDifference,
)


class ResearchSessionLineageComparisonService:
    """
    Compares research sessions using
    lineage and session-owned state.
    """

    COMPARABLE_STATE_FIELDS = (

        "paper_id",

        "paper_title",

        "active_view",

        "selected_object_id",

        "selected_section_id",

        "selected_graph_node_id",
    )

    def __init__(

        self,

        session_manager,

        branch_store,

        lineage_service,

        artifact_store=None,

    ):

        self.session_manager = (
            session_manager
        )

        self.branch_store = (
            branch_store
        )

        self.lineage_service = (
            lineage_service
        )

        self.artifact_store = (
            artifact_store
        )

    def _require_session(

        self,

        session_id: str,

    ):

        session = (

            self.session_manager
            .load_session(

                session_id
            )
        )

        if session is None:

            raise ValueError(

                "Research session "
                "does not exist: "
                f"{session_id}"
            )

        return session

    def _relationship(

        self,

        first_session_id: str,

        second_session_id: str,

    ):

        if (

            first_session_id

            == second_session_id
        ):

            return (

                ResearchSessionRelationship
                .SAME
            )

        if (

            self.lineage_service
            .is_ancestor(

                first_session_id,

                second_session_id,
            )
        ):

            return (

                ResearchSessionRelationship
                .ANCESTOR
            )

        if (

            self.lineage_service
            .is_ancestor(

                second_session_id,

                first_session_id,
            )
        ):

            return (

                ResearchSessionRelationship
                .DESCENDANT
            )

        common = (

            self.lineage_service
            .lowest_common_ancestor(

                first_session_id,

                second_session_id,
            )
        )

        if common is None:

            return (

                ResearchSessionRelationship
                .UNRELATED
            )

        first_parent = (

            self.lineage_service
            .parent_session_id(

                first_session_id
            )
        )

        second_parent = (

            self.lineage_service
            .parent_session_id(

                second_session_id
            )
        )

        if (

            first_parent is not None

            and

            first_parent
            == second_parent
        ):

            return (

                ResearchSessionRelationship
                .SIBLING
            )

        return (

            ResearchSessionRelationship
            .COUSIN
        )

    def _lineage_distance(

        self,

        first_session_id: str,

        second_session_id: str,

    ):

        path = (

            self.lineage_service
            .path_between(

                first_session_id,

                second_session_id,
            )
        )

        if path is None:

            return None

        return path.edge_count

    def _path_from_common_ancestor(

        self,

        common_ancestor_session_id,

        target_session_id,

    ):

        if common_ancestor_session_id is None:

            return []

        root_path = (

            self.lineage_service
            .path_from_root(

                target_session_id
            )
            .session_ids
        )

        index = root_path.index(

            common_ancestor_session_id
        )

        return root_path[
            index:
        ]

    @staticmethod
    def _first_divergent_session(

        path,

    ):

        if len(path) <= 1:

            return None

        return path[1]

    def _branch_origin(

        self,

        session_id: str | None,

    ):

        if session_id is None:

            return None

        return (

            self.branch_store
            .get_by_branch_session(

                session_id
            )
        )

    def _build_divergence(

        self,

        first_session_id: str,

        second_session_id: str,

    ):

        common = (

            self.lineage_service
            .lowest_common_ancestor(

                first_session_id,

                second_session_id,
            )
        )

        first_path = (

            self._path_from_common_ancestor(

                common,

                first_session_id,
            )
        )

        second_path = (

            self._path_from_common_ancestor(

                common,

                second_session_id,
            )
        )

        first_divergent = (

            self._first_divergent_session(

                first_path
            )
        )

        second_divergent = (

            self._first_divergent_session(

                second_path
            )
        )

        first_origin = (

            self._branch_origin(

                first_divergent
            )
        )

        second_origin = (

            self._branch_origin(

                second_divergent
            )
        )

        return (

            ResearchSessionDivergence(

                common_ancestor_session_id=(
                    common
                ),

                first_path_from_common_ancestor=(
                    first_path
                ),

                second_path_from_common_ancestor=(
                    second_path
                ),

                first_divergent_session_id=(
                    first_divergent
                ),

                second_divergent_session_id=(
                    second_divergent
                ),

                first_branch_checkpoint_id=(

                    first_origin
                    .source_checkpoint_id

                    if first_origin

                    else None
                ),

                first_branch_version_id=(

                    first_origin
                    .source_version_id

                    if first_origin

                    else None
                ),

                second_branch_checkpoint_id=(

                    second_origin
                    .source_checkpoint_id

                    if second_origin

                    else None
                ),

                second_branch_version_id=(

                    second_origin
                    .source_version_id

                    if second_origin

                    else None
                ),
            )
        )

    @staticmethod
    def _compare_ids(

        first_ids,

        second_ids,

    ):

        first_set = set(
            first_ids
        )

        second_set = set(
            second_ids
        )

        return (

            ResearchSessionCollectionDifference(

                shared_ids=sorted(

                    first_set
                    & second_set
                ),

                first_only_ids=sorted(

                    first_set
                    - second_set
                ),

                second_only_ids=sorted(

                    second_set
                    - first_set
                ),
            )
        )

    @staticmethod
    def _workflow_step_ids(

        session,

    ):

        steps = getattr(

            session,

            "timeline",

            [],
        )

        return [

            (

                step["id"]

                if isinstance(
                    step,
                    dict,
                )

                else (

                    step.id

                    if hasattr(
                        step,
                        "id",
                    )

                    else str(
                        step
                    )
                )
            )

            for step

            in steps
        ]

    def _artifact_ids(

        self,

        session_id: str,

    ):

        if self.artifact_store is None:

            return []

        artifacts = (

            self.artifact_store
            .list_for_session(

                session_id
            )
        )

        return [

            artifact.id

            for artifact

            in artifacts
        ]

    @staticmethod
    def _knowledge_node_ids(

        session,

    ):

        graph = getattr(

            session,

            "knowledge_graph",

            None,
        )

        if graph is None:

            return []

        return [

            node.id

            for node

            in graph.nodes
        ]

    @staticmethod
    def _knowledge_edge_ids(

        session,

    ):

        graph = getattr(

            session,

            "knowledge_graph",

            None,
        )

        if graph is None:

            return []

        return [

            edge.id

            for edge

            in graph.edges
        ]

    def _compare_state(

        self,

        first_session,

        second_session,

    ):

        differences = []

        for field_name in (

            self.COMPARABLE_STATE_FIELDS
        ):

            first_value = getattr(

                first_session,

                field_name,

                None,
            )

            second_value = getattr(

                second_session,

                field_name,

                None,
            )

            if first_value != second_value:

                differences.append(

                    ResearchSessionStateDifference(

                        field_name=(
                            field_name
                        ),

                        first_value=(
                            first_value
                        ),

                        second_value=(
                            second_value
                        ),
                    )
                )

        return differences

    def compare(

        self,

        first_session_id: str,

        second_session_id: str,

    ) -> ResearchSessionLineageComparison:

        first_session = (

            self._require_session(

                first_session_id
            )
        )

        second_session = (

            self._require_session(

                second_session_id
            )
        )

        relationship = (

            self._relationship(

                first_session_id,

                second_session_id,
            )
        )

        related = (

            relationship

            != (
                ResearchSessionRelationship
                .UNRELATED
            )
        )

        divergence = (

            self._build_divergence(

                first_session_id,

                second_session_id,
            )
        )

        return (

            ResearchSessionLineageComparison(

                first_session_id=(
                    first_session_id
                ),

                second_session_id=(
                    second_session_id
                ),

                relationship=(
                    relationship
                ),

                related=related,

                common_ancestor_session_id=(

                    divergence
                    .common_ancestor_session_id
                ),

                lineage_distance=(

                    self._lineage_distance(

                        first_session_id,

                        second_session_id,
                    )
                ),

                divergence=(
                    divergence
                ),

                state_differences=(

                    self._compare_state(

                        first_session,

                        second_session,
                    )
                ),

                workflow_steps=(

                    self._compare_ids(

                        self._workflow_step_ids(

                            first_session
                        ),

                        self._workflow_step_ids(

                            second_session
                        ),
                    )
                ),

                artifacts=(

                    self._compare_ids(

                        self._artifact_ids(

                            first_session_id
                        ),

                        self._artifact_ids(

                            second_session_id
                        ),
                    )
                ),

                knowledge_nodes=(

                    self._compare_ids(

                        self._knowledge_node_ids(

                            first_session
                        ),

                        self._knowledge_node_ids(

                            second_session
                        ),
                    )
                ),

                knowledge_edges=(

                    self._compare_ids(

                        self._knowledge_edge_ids(

                            first_session
                        ),

                        self._knowledge_edge_ids(

                            second_session
                        ),
                    )
                ),
            )
        )
