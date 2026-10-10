from threading import (
    RLock,
)

from .artifact_promotion import (
    ArtifactPromotion,
)

from .execution_artifact_promotion_error import (
    ExecutionArtifactPromotionError,
)


class ExecutionArtifactPromotionService:
    """
    Promotes verified execution artifact versions between lifecycle
    environments (e.g. staging to production) without creating a new
    version, using an existing execution artifact integrity service
    to confirm a version has a verified checksum before it may be
    promoted.

    The service's responsibility is promotion bookkeeping only. It
    does not verify checksums or move artifact contents itself; it
    relies on the existing execution artifact integrity service,
    given at construction time, only to confirm a version has a
    recorded checksum baseline before it is promoted.

    Behavior:
    - A version may be promoted into any number of distinct
      environments; it is never limited to just one at a time
    - A version may not be promoted into an environment it has
      already been promoted into
    - Every promotion, once created, is immutable and remains in a
      version's history forever

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_integrity_service):
        """
        Args:
            execution_artifact_integrity_service: The service used to
                confirm a version has a verified checksum before it
                is promoted. Any object exposing `status(version_id)`,
                raising if the version has no recorded checksum, is
                accepted
        """

        self._execution_artifact_integrity_service = execution_artifact_integrity_service
        self._promotions_by_version = {}
        self._current_by_artifact_environment = {}
        self._lock = RLock()

    def promote(self, version_id: str, target: str, artifact_id: str) -> ArtifactPromotion:
        """
        Promote a verified version into a target environment.

        Args:
            version_id: The version to promote
            target: The environment to promote it into
            artifact_id: The artifact the version belongs to, used to
                index current() lookups by environment

        Raises:
            ExecutionArtifactPromotionError: If version_id, target, or
                artifact_id is None or blank, the version has no
                recorded checksum, or the version has already been
                promoted into target
        """

        self._validate_id(version_id, "version ID")
        self._validate_id(target, "target")
        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_verified(version_id)

            history = self._promotions_by_version.setdefault(version_id, [])
            existing_targets = {promotion.target for promotion in history}

            if target in existing_targets:
                raise ExecutionArtifactPromotionError(
                    f"Version ID {version_id!r} has already been promoted to environment {target!r}."
                )

            source = history[-1].target if history else None

            promotion = ArtifactPromotion(version_id=version_id, target=target, source=source)

            history.append(promotion)
            self._current_by_artifact_environment[(artifact_id, target)] = promotion

            return promotion

    def history(self, version_id: str) -> list:
        """
        List every promotion of a version, oldest first.

        Raises:
            ExecutionArtifactPromotionError: If version_id is None or
                blank
        """

        self._validate_id(version_id, "version ID")

        with self._lock:
            return list(self._promotions_by_version.get(version_id, []))

    def current(self, artifact_id: str, environment: str) -> ArtifactPromotion:
        """
        Look up the most recent promotion of an artifact into an
        environment.

        Raises:
            ExecutionArtifactPromotionError: If artifact_id or
                environment is None or blank, or no version of the
                artifact has been promoted into it
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(environment, "environment")

        with self._lock:
            promotion = self._current_by_artifact_environment.get((artifact_id, environment))

            if promotion is None:
                raise ExecutionArtifactPromotionError(
                    f"No version of artifact ID {artifact_id!r} has been promoted to environment "
                    f"{environment!r}."
                )

            return promotion

    def _ensure_verified(self, version_id: str) -> None:
        try:
            self._execution_artifact_integrity_service.status(version_id)
        except Exception as error:
            raise ExecutionArtifactPromotionError(
                f"Version ID {version_id!r} is not verified: it has no recorded checksum."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactPromotionError(f"Cannot use an empty or blank {field_name}.")
