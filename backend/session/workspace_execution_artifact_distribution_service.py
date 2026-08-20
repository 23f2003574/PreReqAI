from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .workspace_execution_artifact_distribution import (
    STATUS_FAILED,
    STATUS_PUBLISHED,
    STATUS_REMOVED,
    WorkspaceExecutionArtifactDistribution,
)

from .workspace_execution_artifact_distribution_error import (
    WorkspaceExecutionArtifactDistributionError,
)

from .workspace_execution_artifact_promotion import (
    STAGE_PRODUCTION,
    STATUS_ACTIVE as PROMOTION_STATUS_ACTIVE,
)


class WorkspaceExecutionArtifactDistributionService:
    """
    Makes verified execution artifact versions available at target
    execution environments while preserving their integrity, using an
    existing integrity service, promotion service, and version
    resolver as the sources of truth for a version's verification
    status, promotion history, and recorded checksum.

    The service's responsibility is distribution bookkeeping only. It
    does not transmit artifact contents itself; a distribution
    checksum provider is used to observe what checksum actually landed
    at a target after publishing.

    Behavior:
    - publish() rejects a version that does not currently pass its
      integrity check
    - publish() rejects distributing to PRODUCTION unless the version
      has an ACTIVE promotion to PRODUCTION for its artifact
    - publish() always compares the checksum observed at target
      against the version's recorded checksum after publishing,
      recording PUBLISHED on a match and FAILED on a mismatch
    - A FAILED distribution never blocks a later publish() call to
      the same target: it always remains retryable
    - verify() is read-only: it recomputes the checksum currently
      observed at a distribution's target and compares it to the
      checksum recorded at publish time, without mutating anything
    - targets() reports the targets with a currently PUBLISHED
      distribution for a version, considering only each target's most
      recent attempt

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, integrity_service, promotion_service, version_resolver, checksum_provider):
        """
        Args:
            integrity_service: The service used to confirm a version
                currently passes its integrity check. Any object
                exposing `verify(version_id) -> bool` is accepted
            promotion_service: The service used to confirm a version
                has an ACTIVE promotion to PRODUCTION. Any object
                exposing `history(artifact_id)` (returning an iterable
                of objects with `.version_id`, `.target_stage`, and
                `.status`) is accepted
            version_resolver: The resolver used to look up a
                version's recorded checksum baseline. Any object
                exposing `resolve(version_id)` (returning an object
                with `.checksum`), raising if the version is unknown,
                is accepted
            checksum_provider: The provider used to observe the
                checksum currently present at a target. Any object
                exposing `checksum(version_id, target) -> str` is
                accepted
        """

        self._integrity_service = integrity_service
        self._promotion_service = promotion_service
        self._version_resolver = version_resolver
        self._checksum_provider = checksum_provider
        self._distributions_by_id = {}
        self._distribution_ids_by_version = {}
        self._lock = RLock()

    def publish(self, artifact_id: str, version_id: str, target: str) -> WorkspaceExecutionArtifactDistribution:
        """
        Publish a verified version to a target execution environment.

        Raises:
            WorkspaceExecutionArtifactDistributionError: If
                artifact_id, version_id, or target is None or blank,
                the version fails its integrity check, target is
                PRODUCTION and the version has no ACTIVE promotion to
                PRODUCTION, or the version resolver does not recognize
                version_id
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(version_id, "version ID")
        self._validate_id(target, "target")

        with self._lock:
            self._ensure_verified(version_id)

            if target == STAGE_PRODUCTION:
                self._ensure_promoted(artifact_id, version_id)

            expected_checksum = self._resolve_expected_checksum(version_id)
            actual_checksum = self._resolve_actual_checksum(version_id, target)

            status = STATUS_PUBLISHED if actual_checksum == expected_checksum else STATUS_FAILED

            distribution = WorkspaceExecutionArtifactDistribution(
                artifact_id=artifact_id,
                version_id=version_id,
                target=target,
                status=status,
                checksum=actual_checksum,
            )

            self._distributions_by_id[distribution.distribution_id] = distribution
            self._distribution_ids_by_version.setdefault(version_id, []).append(distribution.distribution_id)

            return distribution

    def verify(self, distribution_id: str) -> bool:
        """
        Check whether the checksum currently observed at a
        distribution's target still matches the checksum recorded at
        publish time. Read-only: never mutates the stored
        distribution.

        Raises:
            WorkspaceExecutionArtifactDistributionError: If
                distribution_id is None or blank, or no distribution
                is registered under it
        """

        self._validate_id(distribution_id, "distribution ID")

        with self._lock:
            distribution = self._resolve(distribution_id)

            current_checksum = self._resolve_actual_checksum(distribution.version_id, distribution.target)

            return current_checksum == distribution.checksum

    def remove(self, distribution_id: str) -> WorkspaceExecutionArtifactDistribution:
        """
        Withdraw a distribution, marking it REMOVED.

        Raises:
            WorkspaceExecutionArtifactDistributionError: If
                distribution_id is None or blank, no distribution is
                registered under it, or it has already been removed
        """

        self._validate_id(distribution_id, "distribution ID")

        with self._lock:
            distribution = self._resolve(distribution_id)

            if distribution.status == STATUS_REMOVED:
                raise WorkspaceExecutionArtifactDistributionError(
                    f"Distribution ID {distribution_id!r} has already been removed."
                )

            removed = replace(distribution, status=STATUS_REMOVED)
            self._distributions_by_id[distribution_id] = removed

            return removed

    def targets(self, version_id: str) -> tuple:
        """
        The targets with a currently PUBLISHED distribution for a
        version, considering only each target's most recent attempt.

        Raises:
            WorkspaceExecutionArtifactDistributionError: If version_id
                is None or blank
        """

        self._validate_id(version_id, "version ID")

        with self._lock:
            latest_by_target = {}

            for distribution_id in self._distribution_ids_by_version.get(version_id, []):
                distribution = self._distributions_by_id[distribution_id]
                latest_by_target[distribution.target] = distribution

            return tuple(
                target for target, distribution in latest_by_target.items() if distribution.status == STATUS_PUBLISHED
            )

    def _ensure_verified(self, version_id: str) -> None:
        try:
            verified = self._integrity_service.verify(version_id)
        except Exception as error:
            raise WorkspaceExecutionArtifactDistributionError(
                f"Cannot verify version ID {version_id!r}: it failed its integrity check."
            ) from error

        if not verified:
            raise WorkspaceExecutionArtifactDistributionError(
                f"Cannot publish version ID {version_id!r}: it failed its integrity check."
            )

    def _ensure_promoted(self, artifact_id: str, version_id: str) -> None:
        try:
            promotions = self._promotion_service.history(artifact_id)
        except Exception as error:
            raise WorkspaceExecutionArtifactDistributionError(
                f"Cannot confirm a PRODUCTION promotion for version ID {version_id!r}."
            ) from error

        promoted = any(
            promotion.version_id == version_id
            and promotion.target_stage == STAGE_PRODUCTION
            and promotion.status == PROMOTION_STATUS_ACTIVE
            for promotion in promotions
        )

        if not promoted:
            raise WorkspaceExecutionArtifactDistributionError(
                f"Cannot publish version ID {version_id!r} to PRODUCTION: it has no ACTIVE "
                f"promotion to PRODUCTION."
            )

    def _resolve_expected_checksum(self, version_id: str) -> str:
        try:
            return self._version_resolver.resolve(version_id).checksum
        except Exception as error:
            raise WorkspaceExecutionArtifactDistributionError(
                f"No version is known under version ID {version_id!r}."
            ) from error

    def _resolve_actual_checksum(self, version_id: str, target: str) -> str:
        try:
            return self._checksum_provider.checksum(version_id, target)
        except Exception as error:
            raise WorkspaceExecutionArtifactDistributionError(
                f"Cannot observe a checksum for version ID {version_id!r} at target {target!r}."
            ) from error

    def _resolve(self, distribution_id: str) -> WorkspaceExecutionArtifactDistribution:
        distribution = self._distributions_by_id.get(distribution_id)

        if distribution is None:
            raise WorkspaceExecutionArtifactDistributionError(
                f"No distribution is registered under distribution ID {distribution_id!r}."
            )

        return distribution

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactDistributionError(f"Cannot use an empty or blank {field_name}.")
