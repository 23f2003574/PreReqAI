from dataclasses import (
    dataclass,
    field,
)

from typing import Any

from .learning_content_type import (
    LearningContentType,
)


@dataclass
class LearningContent:
    """
    Represents one contextual educational
    output displayed in the workspace.
    """

    id: str

    title: str

    content_type: LearningContentType

    body: Any

    object_id: str | None = None

    action: str | None = None

    workflow: str | None = None

    metadata: dict = field(
        default_factory=dict,
    )
