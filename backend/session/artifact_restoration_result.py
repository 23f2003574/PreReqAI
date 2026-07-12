from dataclasses import (
    dataclass,
    field,
)

from typing import Any


@dataclass
class ArtifactRestorationResult:
    """
    Describes the outcome of restoring
    durable research artifacts into
    the active learning workspace.
    """

    restored: bool

    interaction_id: str | None = None

    artifacts: list[Any] = field(
        default_factory=list,
    )

    learning_content: list[Any] = field(
        default_factory=list,
    )

    missing_artifact_ids: list[str] = field(
        default_factory=list,
    )
