from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .execution_artifact_garbage_collection_error import (
    ExecutionArtifactGarbageCollectionError,
)

from .execution_artifact_garbage_record import (
    REASON_RETENTION_EXPIRED,
    ExecutionArtifactGarbageRecord,
)

from .workspace_execution_artifact_promotion import (
    STAGE_PRODUCTION,
    STATUS_ACTIVE as PROMOTION_STATUS_ACTIVE,
)


class ExecutionArtifactGarbageCollectionService:
    """
    Reclaims artifact versions that have passed retention and are no
    longer protected, using an existing version service, retention
    service, version resolver, and promotion service as the sources
    of truth for a version's existence, retention eligibility, and
    production status.

    The service's responsibility is scan/mark/collect bookkeeping
    only. It does not delete artifact contents itself; collect()
    tracks, for each marked record, that it has been reclaimed by
    setting deleted_at.

    Behavior:
    - scan() reports which of an artifact's versions are currently
      retention-expired and unprotected, without marking anything
    - mark() is the only way to stage a version for deletion, and
      refuses a version that is still protected; marking the same
      version twice returns the original record rather than creating
      a duplicate
    - collect() only deletes versions that have already been marked;
      it re-checks protection at collection time and skips (rather
      than deletes) a version that has since become protected
    - collect() is idempotent: a record already deleted is left
      untouched and is not reported again
    - protected() checks both retention eligibility and direct
      production status, so a version is never collected while either
      says to keep it

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, version_service, version_resolver, retention_service, promotion_service):
        """
        Args:
            version_service: The service used to enumerate an
                artifact's versions. Any object exposing
                `history(artifact_id)` (returning an iterable of
                objects with `.version_id`) is accepted
            version_resolver: The resolver used to look up a bare
                version_id's owning artifact. Any object exposing
                `resolve(version_id)` (returning an object with
                `.artifact_id`), raising if the version is unknown, is
                accepted
            retention_service: The service used to confirm a version
                still respects its retention policy. Any object
                exposing `eligible(version_id) -> bool` is accepted
            promotion_service: The service used to confirm whether a
                version is currently ACTIVE at PRODUCTION. Any object
                exposing `history(artifact_id)` (returning an iterable
                of objects with `.version_id`, `.target_stage`, and
                `.status`) is accepted
        """

        self._version_service = version_service
        self._version_resolver = version_resolver
        self._retention_service = retention_service
        self._promotion_service = promotion_service
        self._records_by_version = {}
        self._record_ids_by_artifact = {}
        self._lock = RLock()

    def scan(self, artifact_id: str) -> tuple:
        """
        List the version IDs of artifact_id that are currently
        retention-expired and unprotected. Read-only: marks nothing.

        Raises:
            ExecutionArtifactGarbageCollectionError: If artifact_id is
                None or blank
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            versions = self._version_service.history(artifact_id)

            return tuple(
                version.version_id
                for version in versions
                if not self._is_protected(artifact_id, version.version_id)
            )

    def mark(self, version_id: str) -> ExecutionArtifactGarbageRecord:
        """
        Stage a retention-expired, unprotected version for deletion.

        Raises:
            ExecutionArtifactGarbageCollectionError: If version_id is
                None or blank, the version resolver does not recognize
                version_id, or the version is currently protected
        """

        self._validate_id(version_id, "version ID")

        with self._lock:
            existing = self._records_by_version.get(version_id)

            if existing is not None and existing.deleted_at is None:
                return existing

            artifact_id = self._resolve_artifact_id(version_id)

            if self._is_protected(artifact_id, version_id):
                raise ExecutionArtifactGarbageCollectionError(
                    f"Cannot mark version ID {version_id!r}: it is currently protected."
                )

            record = ExecutionArtifactGarbageRecord(
                artifact_id=artifact_id,
                version_id=version_id,
                reason=REASON_RETENTION_EXPIRED,
            )

            self._records_by_version[version_id] = record

            ids = self._record_ids_by_artifact.setdefault(artifact_id, [])

            if version_id not in ids:
                ids.append(version_id)

            return record

    def collect(self, artifact_id: str) -> tuple:
        """
        Delete every version of artifact_id that has been marked but
        not yet deleted and remains unprotected. Idempotent: a
        version already deleted, or a version_id not currently
        marked, is left untouched.

        Returns:
            The records newly deleted by this call

        Raises:
            ExecutionArtifactGarbageCollectionError: If artifact_id is
                None or blank
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            collected = []

            for version_id in self._record_ids_by_artifact.get(artifact_id, []):
                record = self._records_by_version[version_id]

                if record.deleted_at is not None:
                    continue

                if self._is_protected(artifact_id, version_id):
                    continue

                deleted = replace(record, deleted_at=datetime.now(timezone.utc))
                self._records_by_version[version_id] = deleted
                collected.append(deleted)

            return tuple(collected)

    def protected(self, version_id: str) -> bool:
        """
        Whether a version is currently protected from garbage
        collection, either because it still respects its retention
        policy or because it is ACTIVE at PRODUCTION.

        Raises:
            ExecutionArtifactGarbageCollectionError: If version_id is
                None or blank, or the version resolver does not
                recognize version_id
        """

        self._validate_id(version_id, "version ID")

        with self._lock:
            artifact_id = self._resolve_artifact_id(version_id)

            return self._is_protected(artifact_id, version_id)

    def history(self, artifact_id: str) -> tuple:
        """
        List every garbage record for an artifact, marked or
        deleted, oldest to newest.

        Raises:
            ExecutionArtifactGarbageCollectionError: If artifact_id is
                None or blank
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            return tuple(
                self._records_by_version[version_id]
                for version_id in self._record_ids_by_artifact.get(artifact_id, [])
            )

    def _is_protected(self, artifact_id: str, version_id: str) -> bool:
        if self._retention_eligible(version_id):
            return True

        return self._is_production_active(artifact_id, version_id)

    def _retention_eligible(self, version_id: str) -> bool:
        try:
            return bool(self._retention_service.eligible(version_id))
        except Exception as error:
            raise ExecutionArtifactGarbageCollectionError(
                f"Cannot evaluate retention eligibility for version ID {version_id!r}."
            ) from error

    def _is_production_active(self, artifact_id: str, version_id: str) -> bool:
        try:
            promotions = self._promotion_service.history(artifact_id)
        except Exception:
            return False

        return any(
            promotion.version_id == version_id
            and promotion.target_stage == STAGE_PRODUCTION
            and promotion.status == PROMOTION_STATUS_ACTIVE
            for promotion in promotions
        )

    def _resolve_artifact_id(self, version_id: str) -> str:
        try:
            return self._version_resolver.resolve(version_id).artifact_id
        except Exception as error:
            raise ExecutionArtifactGarbageCollectionError(
                f"No version is known under version ID {version_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactGarbageCollectionError(f"Cannot use an empty or blank {field_name}.")
