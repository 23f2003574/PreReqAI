from dataclasses import dataclass, field


@dataclass
class WorkflowExecutionResult:
    """
    Aggregated result produced by a
    multi-workflow learning session.
    """

    responses: list = field(
        default_factory=list,
    )

    executed_workflows: list[str] = field(
        default_factory=list,
    )
