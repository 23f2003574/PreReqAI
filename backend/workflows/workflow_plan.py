from dataclasses import dataclass, field

from backend.session import (
    WorkflowType,
)


@dataclass
class WorkflowPlan:
    """
    Ordered execution plan for a learner request.
    """

    workflows: list[WorkflowType] = field(
        default_factory=list,
    )
