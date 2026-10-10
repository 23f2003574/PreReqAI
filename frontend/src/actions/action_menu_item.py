from dataclasses import dataclass

from backend.interaction import (
    ObjectAction,
)


@dataclass
class ActionMenuItem:
    """
    Represents one executable action
    displayed for a research object.
    """

    action: ObjectAction

    label: str

    enabled: bool = True
