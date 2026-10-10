from dataclasses import (
    dataclass,
    field,
)

from .research_session_collection_difference import (
    ResearchSessionCollectionDifference,
)

from .research_session_divergence import (
    ResearchSessionDivergence,
)

from .research_session_relationship import (
    ResearchSessionRelationship,
)

from .research_session_state_difference import (
    ResearchSessionStateDifference,
)


@dataclass
class ResearchSessionLineageComparison:
    """
    Represents a complete derived
    comparison between two research
    sessions.
    """

    first_session_id: str

    second_session_id: str

    relationship: (
        ResearchSessionRelationship
    )

    related: bool

    common_ancestor_session_id: (
        str | None
    )

    lineage_distance: (
        int | None
    )

    divergence: (
        ResearchSessionDivergence
    )

    state_differences: list[
        ResearchSessionStateDifference
    ] = field(
        default_factory=list,
    )

    workflow_steps: (
        ResearchSessionCollectionDifference
    ) = (
        field(
            default_factory=(
                ResearchSessionCollectionDifference
            )
        )
    )

    artifacts: (
        ResearchSessionCollectionDifference
    ) = (
        field(
            default_factory=(
                ResearchSessionCollectionDifference
            )
        )
    )

    knowledge_nodes: (
        ResearchSessionCollectionDifference
    ) = (
        field(
            default_factory=(
                ResearchSessionCollectionDifference
            )
        )
    )

    knowledge_edges: (
        ResearchSessionCollectionDifference
    ) = (
        field(
            default_factory=(
                ResearchSessionCollectionDifference
            )
        )
    )

    @property
    def has_differences(self):

        return bool(

            self.state_differences

            or self.workflow_steps.differs

            or self.artifacts.differs

            or self.knowledge_nodes.differs

            or self.knowledge_edges.differs
        )

    def to_dict(self):

        return {

            "first_session_id":
                self.first_session_id,

            "second_session_id":
                self.second_session_id,

            "relationship":
                self.relationship.value,

            "related":
                self.related,

            "common_ancestor_session_id":
                self.common_ancestor_session_id,

            "lineage_distance":
                self.lineage_distance,

            "divergence":
                self.divergence.to_dict(),

            "state_differences": [

                difference.to_dict()

                for difference

                in self.state_differences
            ],

            "workflow_steps":
                self.workflow_steps.to_dict(),

            "artifacts":
                self.artifacts.to_dict(),

            "knowledge_nodes":
                self.knowledge_nodes.to_dict(),

            "knowledge_edges":
                self.knowledge_edges.to_dict(),

            "has_differences":
                self.has_differences,
        }
