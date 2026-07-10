from dataclasses import dataclass, field

from .object_action import (
    ObjectAction,
)


@dataclass
class InteractionPlan:
    """
    Ordered educational interaction plan.
    """

    actions: list[
        ObjectAction
    ] = field(
        default_factory=list,
    )
