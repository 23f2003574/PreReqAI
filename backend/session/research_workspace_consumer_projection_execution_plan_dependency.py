from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionPlanDependency:
    """
    A required dependency resolved as part of
    planning a consumer projection execution.

    Attributes:
        name: Identifies the dependency
        satisfied: Whether the dependency is available at all
        degraded: Whether the dependency is only reachable via a
            degraded path (satisfied, but not at full strength)
    """

    name: str

    satisfied: bool

    degraded: bool = False

    def to_dict(self):
        return {
            "name": self.name,
            "satisfied": self.satisfied,
            "degraded": self.degraded,
        }
