from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_health import (
    ResearchWorkspaceConsumerProjectionExecutionHealth,
)

from .research_workspace_consumer_projection_health_transition_kind import (
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionHealthTransition:
    """
    Result of comparing two consumer projection execution health
    summaries.

    Describes the direction of health movement between a previous
    and a current execution of the same projection - compact and
    intentionally shallower than Commit #1's receipt comparison,
    which compares detailed execution characteristics rather than
    a single overall health classification.

    Attributes:
        projection_name: Name of the compared projection
        previous_execution_id: Execution ID of the previous health summary
        current_execution_id: Execution ID of the current health summary
        previous_health: Health classification of the previous execution
        current_health: Health classification of the current execution
        kind: Directional classification of the health movement
    """

    projection_name: str

    previous_execution_id: str

    current_execution_id: str

    previous_health: (
        ResearchWorkspaceConsumerProjectionExecutionHealth
    )

    current_health: (
        ResearchWorkspaceConsumerProjectionExecutionHealth
    )

    kind: (
        ResearchWorkspaceConsumerProjectionHealthTransitionKind
    )

    @property
    def changed(self) -> bool:
        return self.previous_health != self.current_health

    def to_dict(self):
        """
        Serialize the health transition to a deterministic dictionary.
        """

        return {
            "projection_name": self.projection_name,
            "previous_execution_id": self.previous_execution_id,
            "current_execution_id": self.current_execution_id,
            "previous_health": self.previous_health.value,
            "current_health": self.current_health.value,
            "kind": self.kind.value,
            "changed": self.changed,
        }
