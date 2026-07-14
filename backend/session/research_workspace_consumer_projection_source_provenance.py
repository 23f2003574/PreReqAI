from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_freshness_status import (
    ResearchWorkspaceConsumerProjectionFreshnessStatus,
)


@dataclass
class ResearchWorkspaceConsumerProjectionSourceProvenance:
    """
    Identifies one request-scoped
    observation used as evidence. Never
    carries the raw resolved value —
    only enough to identify which
    observation contributed.
    """

    node_id: str

    source_name: str

    source_timestamp: object = None

    freshness_status: (
        ResearchWorkspaceConsumerProjectionFreshnessStatus
        | None
    ) = None

    def to_dict(self):

        return {

            "node_id":
                self.node_id,

            "source_name":
                self.source_name,

            "source_timestamp": (

                self.source_timestamp
                .isoformat()

                if self.source_timestamp

                is not None

                else None
            ),

            "freshness_status": (

                self.freshness_status
                .value

                if self.freshness_status

                is not None

                else None
            ),
        }
