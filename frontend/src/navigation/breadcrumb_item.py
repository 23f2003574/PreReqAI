from dataclasses import dataclass

from typing import Any


@dataclass
class BreadcrumbItem:
    """
    Represents one navigable location
    inside the current research path.
    """

    id: str

    label: str

    context_type: str

    source: Any = None
