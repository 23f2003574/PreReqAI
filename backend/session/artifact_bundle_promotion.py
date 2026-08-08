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

from .execution_artifact_bundle_promotion_error import (
    ExecutionArtifactBundlePromotionError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "PROMOTED",
        "ROLLED_BACK",
    }
)


@dataclass(frozen=True)
class ArtifactBundlePromotion:
    """
    Immutable record of a complete, verified artifact bundle being
    promoted, atomically, from one lifecycle environment to another.

    The promotion is a value object only. It performs no promotion
    of its own; creating, rolling back, and looking up bundle
    promotions is the responsibility of an execution artifact bundle
    promotion service.

    Attributes:
        promotion_id: The promotion's unique identifier
        bundle_id: The identifier of the bundle being promoted
        source: The environment the bundle was promoted from, or
            None if this is its first promotion
        target: The environment the bundle was promoted to
        promoted_at: When this promotion took place
        status: The promotion's current status, PROMOTED or
            ROLLED_BACK
    """

    bundle_id: str

    target: str

    source: Optional[str]

    promotion_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    promoted_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    status: str = "PROMOTED"

    def __post_init__(self):
        self._require_text(self.promotion_id, "promotion ID")
        self._require_text(self.bundle_id, "bundle ID")
        self._require_text(self.target, "target")
        self._require_text(self.status, "status")

        if self.source is not None:
            self._require_text(self.source, "source")

        if self.source is not None and self.source == self.target:
            raise ExecutionArtifactBundlePromotionError(
                f"Cannot promote bundle ID {self.bundle_id!r} to environment {self.target!r}: "
                "it is already there."
            )

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionArtifactBundlePromotionError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if not isinstance(self.promoted_at, datetime):
            raise ExecutionArtifactBundlePromotionError(
                "Cannot build a bundle promotion with a non-datetime promoted_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactBundlePromotionError(
                f"Cannot build a bundle promotion with an empty or blank {field_name}."
            )
