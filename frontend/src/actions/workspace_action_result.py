from dataclasses import dataclass

from typing import Any


@dataclass
class WorkspaceActionResult:
    """
    Represents the result of executing
    an educational action from the
    visual workspace.
    """

    object_id: str

    action: str

    response: Any
