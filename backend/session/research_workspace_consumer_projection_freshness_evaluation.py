from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_freshness_reason import (
    ResearchWorkspaceConsumerProjectionFreshnessReason,
)

from .research_workspace_consumer_projection_freshness_status import (
    ResearchWorkspaceConsumerProjectionFreshnessStatus,
)


@dataclass
class ResearchWorkspaceConsumerProjectionFreshnessEvaluation:
    """
    The immutable result of evaluating
    one source timestamp against its
    freshness policy at a stable
    operation observation time.
    """

    source_name: str

    status: (
        ResearchWorkspaceConsumerProjectionFreshnessStatus
    )

    reason: (
        ResearchWorkspaceConsumerProjectionFreshnessReason
    )

    source_timestamp: object

    evaluated_at: object

    age_ms: float

    fresh_for_ms: float

    usable_for_ms: float

    def to_dict(self):

        return {

            "source_name":
                self.source_name,

            "status":
                self.status.value,

            "reason":
                self.reason.value,

            "source_timestamp":
                self.source_timestamp
                .isoformat(),

            "evaluated_at":
                self.evaluated_at
                .isoformat(),

            "age_ms":
                self.age_ms,

            "fresh_for_ms":
                self.fresh_for_ms,

            "usable_for_ms":
                self.usable_for_ms,
        }
