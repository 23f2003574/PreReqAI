from dataclasses import dataclass

from typing import Any


@dataclass
class InspectorField:
    """
    Represents one contextual field
    displayed inside the research
    object inspector.
    """

    label: str

    value: Any
