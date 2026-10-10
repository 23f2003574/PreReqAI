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

from .workspace_execution_artifact_promotion_error import (
    WorkspaceExecutionArtifactPromotionError,
)

STAGE_DEV = "DEV"

STAGE_STAGING = "STAGING"

STAGE_PRODUCTION = "PRODUCTION"

STAGES = (
    STAGE_DEV,
    STAGE_STAGING,
    STAGE_PRODUCTION,
)

STATUS_ACTIVE = "ACTIVE"

STATUS_ROLLED_BACK = "ROLLED_BACK"

STATUSES = (
    STATUS_ACTIVE,
    STATUS_ROLLED_BACK,
)


@dataclass(frozen=True)
class WorkspaceExecutionArtifactPromotion:
    """
    Immutable record of a single move of a verified artifact version
    from one lifecycle stage to a later one, without modifying the
    version's contents.

    The promotion is a value object only. It performs no integrity
    verification of its own; promoting, looking up, and rolling back
    promotions is the responsibility of an execution artifact
    promotion service.

    Attributes:
        artifact_id: The identifier of the artifact whose version was
            promoted
        version_id: The identifier of the version that was promoted
        target_stage: The stage the version was promoted into, one of
            STAGES
        source_stage: The stage the version was promoted from, one of
            STAGES, or None if this is its first promotion
        status: ACTIVE until this promotion is rolled back, one of
            STATUSES
        promotion_id: The promotion's unique identifier
        promoted_at: When this promotion was recorded
    """

    artifact_id: str

    version_id: str

    target_stage: str

    source_stage: Optional[str] = None

    status: str = STATUS_ACTIVE

    promotion_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    promoted_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.promotion_id, "promotion ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.version_id, "version ID")

        if self.target_stage not in STAGES:
            raise WorkspaceExecutionArtifactPromotionError(
                f"Cannot build a workspace execution artifact promotion with an unknown target "
                f"stage: {self.target_stage!r}."
            )

        if self.source_stage is not None:
            if self.source_stage not in STAGES:
                raise WorkspaceExecutionArtifactPromotionError(
                    f"Cannot build a workspace execution artifact promotion with an unknown "
                    f"source stage: {self.source_stage!r}."
                )

            if STAGES.index(self.source_stage) >= STAGES.index(self.target_stage):
                raise WorkspaceExecutionArtifactPromotionError(
                    f"Cannot build a workspace execution artifact promotion moving backward or "
                    f"sideways from {self.source_stage!r} to {self.target_stage!r}: promotion "
                    f"only moves forward."
                )

        if self.status not in STATUSES:
            raise WorkspaceExecutionArtifactPromotionError(
                f"Cannot build a workspace execution artifact promotion with an unknown status: "
                f"{self.status!r}."
            )

        if not isinstance(self.promoted_at, datetime):
            raise WorkspaceExecutionArtifactPromotionError(
                "Cannot build a workspace execution artifact promotion with a non-datetime "
                "promoted_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactPromotionError(
                f"Cannot build a workspace execution artifact promotion with an empty or blank "
                f"{field_name}."
            )
