from dataclasses import dataclass
from typing import Optional


@dataclass
class ActionExecutionResult:
    """
    Represents the outcome of an
    educational interaction.
    """

    object_id: str

    action: str

    workflow: Optional[str]

    response: Optional[object] = None
