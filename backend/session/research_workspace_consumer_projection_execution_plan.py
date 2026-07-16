from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_plan_dependency import (
    ResearchWorkspaceConsumerProjectionExecutionPlanDependency,
)

from .research_workspace_consumer_projection_execution_plan_source import (
    ResearchWorkspaceConsumerProjectionExecutionPlanSource,
)

from .research_workspace_consumer_projection_execution_plan_stage import (
    ResearchWorkspaceConsumerProjectionExecutionPlanStage,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionPlan:
    """
    The resolved planning artifact for one consumer projection
    execution, produced upstream of readiness evaluation.

    Carries only already-resolved planning facts - it does not
    itself resolve dependencies, sources, budget, or stages.

    Attributes:
        projection_name: Identifies the projection being planned
        enabled: Whether the projection is enabled at all
        budget_available: Whether execution budget remains
        required_dependencies: Dependencies the plan cannot omit
        required_sources: Sources the plan cannot omit
        stages: Planned execution stages, mandatory and optional
    """

    projection_name: str

    enabled: bool

    budget_available: bool

    required_dependencies: tuple[
        ResearchWorkspaceConsumerProjectionExecutionPlanDependency,
        ...,
    ] = ()

    required_sources: tuple[
        ResearchWorkspaceConsumerProjectionExecutionPlanSource,
        ...,
    ] = ()

    stages: tuple[
        ResearchWorkspaceConsumerProjectionExecutionPlanStage,
        ...,
    ] = ()

    def to_dict(self):
        return {
            "projection_name": self.projection_name,
            "enabled": self.enabled,
            "budget_available": self.budget_available,
            "required_dependencies": [
                dependency.to_dict()
                for dependency in self.required_dependencies
            ],
            "required_sources": [
                source.to_dict()
                for source in self.required_sources
            ],
            "stages": [
                stage.to_dict()
                for stage in self.stages
            ],
        }
