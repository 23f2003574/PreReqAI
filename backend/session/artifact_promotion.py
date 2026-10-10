from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import Optional
from uuid import uuid4

from .execution_artifact_promotion_error import (
    ExecutionArtifactPromotionError,
)


@dataclass(frozen=True)
class ArtifactPromotion:
    """
    Immutable record of a verified artifact version being promoted
    from one lifecycle environment to another, without creating a
    new version.

    The promotion is a value object only. It performs no promotion
    of its own; creating and looking up promotions is the
    responsibility of an execution artifact promotion service.

    Attributes:
        promotion_id: The promotion's unique identifier
        version_id: The identifier of the execution artifact version
            being promoted
        source: The environment the version was promoted from, or
            None if this is its first promotion
        target: The environment the version was promoted to
        promoted_at: When this promotion took place
    """

    version_id: str

    target: str

    source: Optional[str]

    promotion_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    promoted_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.promotion_id, "promotion ID")
        self._require_text(self.version_id, "version ID")
        self._require_text(self.target, "target")

        if self.source is not None:
            self._require_text(self.source, "source")

        if self.source is not None and self.source == self.target:
            raise ExecutionArtifactPromotionError(
                f"Cannot promote version ID {self.version_id!r} to environment {self.target!r}: "
                "it is already there."
            )

        if not isinstance(self.promoted_at, datetime):
            raise ExecutionArtifactPromotionError(
                "Cannot build an artifact promotion with a non-datetime promoted_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactPromotionError(
                f"Cannot build an artifact promotion with an empty or blank {field_name}."
            )
