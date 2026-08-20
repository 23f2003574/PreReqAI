from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .workspace_execution_artifact_promotion import (
    STAGE_PRODUCTION,
    STAGES,
    STATUS_ACTIVE,
    STATUS_ROLLED_BACK,
    WorkspaceExecutionArtifactPromotion,
)

from .workspace_execution_artifact_promotion_error import (
    WorkspaceExecutionArtifactPromotionError,
)


class WorkspaceExecutionArtifactPromotionService:
    """
    Promotes verified execution artifact versions between lifecycle
    stages (DEV, STAGING, PRODUCTION) without modifying their
    contents, using an existing artifact registry to confirm an
    artifact is known and an existing integrity service to confirm a
    version currently passes its integrity check before it may be
    promoted.

    The service's responsibility is promotion bookkeeping only. It
    does not verify checksums or move artifact contents itself.

    Behavior:
    - promote() only ever moves a version forward through STAGES; it
      never allows a sideways or backward move
    - A version already ACTIVE at PRODUCTION cannot be promoted again:
      production versions cannot be modified
    - rollback() reverses a promotion by marking it ROLLED_BACK, but
      refuses to touch a PRODUCTION promotion, preserving production
      immutability
    - Every promotion, once created, keeps its original fields
      forever; only its status may later transition to ROLLED_BACK

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, artifact_registry_service, integrity_service):
        """
        Args:
            artifact_registry_service: The registry used to confirm
                an artifact ID is known and active before a version is
                promoted. Any object exposing `get(artifact_id)`,
                raising if the artifact is unknown or removed, is
                accepted
            integrity_service: The service used to confirm a version
                currently passes its integrity check. Any object
                exposing `verify(version_id) -> bool` is accepted
        """

        self._artifact_registry_service = artifact_registry_service
        self._integrity_service = integrity_service
        self._promotions_by_id = {}
        self._promotion_ids_by_version = {}
        self._promotion_ids_by_artifact = {}
        self._lock = RLock()

    def promote(self, artifact_id: str, version_id: str, target_stage: str) -> WorkspaceExecutionArtifactPromotion:
        """
        Promote a verified version forward into target_stage.

        Raises:
            WorkspaceExecutionArtifactPromotionError: If artifact_id
                or version_id is None or blank, target_stage is not
                one of STAGES, the artifact registry does not
                recognize artifact_id as active, the version fails its
                integrity check, the version is already ACTIVE at
                PRODUCTION, or target_stage is not strictly forward of
                the version's current stage
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(version_id, "version ID")

        if target_stage not in STAGES:
            raise WorkspaceExecutionArtifactPromotionError(
                f"Cannot promote to an unknown stage: {target_stage!r}."
            )

        with self._lock:
            self._ensure_artifact_known(artifact_id)
            self._ensure_verified(version_id)

            key = (artifact_id, version_id)
            active = self._active_promotions(key)

            if any(promotion.target_stage == STAGE_PRODUCTION for promotion in active):
                raise WorkspaceExecutionArtifactPromotionError(
                    f"Version ID {version_id!r} is already in PRODUCTION: production versions "
                    f"cannot be modified."
                )

            current_index = max((STAGES.index(promotion.target_stage) for promotion in active), default=-1)
            target_index = STAGES.index(target_stage)

            if target_index <= current_index:
                raise WorkspaceExecutionArtifactPromotionError(
                    f"Cannot promote version ID {version_id!r} to {target_stage!r}: promotion "
                    f"only moves forward."
                )

            source_stage = STAGES[current_index] if current_index >= 0 else None

            promotion = WorkspaceExecutionArtifactPromotion(
                artifact_id=artifact_id,
                version_id=version_id,
                source_stage=source_stage,
                target_stage=target_stage,
            )

            self._promotions_by_id[promotion.promotion_id] = promotion
            self._promotion_ids_by_version.setdefault(key, []).append(promotion.promotion_id)
            self._promotion_ids_by_artifact.setdefault(artifact_id, []).append(promotion.promotion_id)

            return promotion

    def status(self, promotion_id: str) -> WorkspaceExecutionArtifactPromotion:
        """
        Look up a promotion by ID.

        Raises:
            WorkspaceExecutionArtifactPromotionError: If promotion_id
                is None or blank, or no promotion is registered under
                it
        """

        self._validate_id(promotion_id, "promotion ID")

        with self._lock:
            return self._resolve(promotion_id)

    def history(self, artifact_id: str) -> tuple:
        """
        List every promotion recorded for any version of an artifact,
        oldest to newest.

        Raises:
            WorkspaceExecutionArtifactPromotionError: If artifact_id
                is None or blank
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            return tuple(
                self._promotions_by_id[promotion_id]
                for promotion_id in self._promotion_ids_by_artifact.get(artifact_id, [])
            )

    def rollback(self, promotion_id: str) -> WorkspaceExecutionArtifactPromotion:
        """
        Reverse a promotion, marking it ROLLED_BACK.

        Raises:
            WorkspaceExecutionArtifactPromotionError: If promotion_id
                is None or blank, no promotion is registered under it,
                it has already been rolled back, or it promoted a
                version into PRODUCTION
        """

        self._validate_id(promotion_id, "promotion ID")

        with self._lock:
            promotion = self._resolve(promotion_id)

            if promotion.status != STATUS_ACTIVE:
                raise WorkspaceExecutionArtifactPromotionError(
                    f"Promotion ID {promotion_id!r} has already been rolled back."
                )

            if promotion.target_stage == STAGE_PRODUCTION:
                raise WorkspaceExecutionArtifactPromotionError(
                    f"Cannot roll back promotion ID {promotion_id!r}: production versions cannot "
                    f"be modified."
                )

            rolled_back = replace(promotion, status=STATUS_ROLLED_BACK)
            self._promotions_by_id[promotion_id] = rolled_back

            return rolled_back

    def _active_promotions(self, key) -> tuple:
        return tuple(
            self._promotions_by_id[promotion_id]
            for promotion_id in self._promotion_ids_by_version.get(key, [])
            if self._promotions_by_id[promotion_id].status == STATUS_ACTIVE
        )

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._artifact_registry_service.get(artifact_id)
        except Exception as error:
            raise WorkspaceExecutionArtifactPromotionError(
                f"No active artifact is known under artifact ID {artifact_id!r}."
            ) from error

    def _ensure_verified(self, version_id: str) -> None:
        try:
            verified = self._integrity_service.verify(version_id)
        except Exception as error:
            raise WorkspaceExecutionArtifactPromotionError(
                f"Cannot verify version ID {version_id!r}: it failed its integrity check."
            ) from error

        if not verified:
            raise WorkspaceExecutionArtifactPromotionError(
                f"Cannot promote version ID {version_id!r}: it failed its integrity check."
            )

    def _resolve(self, promotion_id: str) -> WorkspaceExecutionArtifactPromotion:
        promotion = self._promotions_by_id.get(promotion_id)

        if promotion is None:
            raise WorkspaceExecutionArtifactPromotionError(
                f"No promotion is registered under promotion ID {promotion_id!r}."
            )

        return promotion

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactPromotionError(f"Cannot use an empty or blank {field_name}.")
