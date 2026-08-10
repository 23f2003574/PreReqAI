from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_artifact_mount import (
    ExecutionArtifactMount,
)

from .execution_artifact_mount_error import (
    ExecutionArtifactMountError,
)

from .execution_artifact_retrieval_request import (
    ExecutionArtifactRetrievalRequest,
)

_DEFAULT_TTL = timedelta(minutes=15)


class ExecutionArtifactMountService:
    """
    Exposes retrieved execution artifacts to consumers through
    temporary mounts, each backed by an existing execution artifact
    retrieval service to confirm the consumer may retrieve the
    artifact before a mount is created.

    The service's responsibility is mount bookkeeping only. It does
    not retrieve, store, or mutate artifacts themselves; it relies on
    the existing execution artifact retrieval service, given at
    construction time, only to confirm retrieval permission before a
    mount is created.

    Behavior:
    - mount() requires the consumer to already have retrieval
      permission for the artifact
    - An artifact/consumer pair may have at most one active mount at
      a time; mounting an already actively-mounted pair is rejected
    - A mount expires automatically once its expires_at has passed;
      an expired mount is no longer considered active and its slot
      may be mounted again
    - unmount() releases a mount immediately, regardless of whether
      it has expired
    - mounts() lists only a consumer's currently active mounts,
      isolated from every other consumer's mounts
    - expired() lists every currently expired mount that has not yet
      been cleaned up, across all consumers
    - cleanup() releases every currently expired mount

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_retrieval_service, ttl: timedelta = _DEFAULT_TTL):
        """
        Args:
            execution_artifact_retrieval_service: The service used to
                confirm a consumer may retrieve an artifact before a
                mount is created on their behalf. Any object exposing
                `retrieve(request)`, raising if retrieval is denied
                or the artifact is unknown, is accepted
            ttl: How long a newly created mount stays active before
                it expires
        """

        if not isinstance(ttl, timedelta):
            raise ExecutionArtifactMountError("Cannot use a non-timedelta ttl.")

        self._execution_artifact_retrieval_service = execution_artifact_retrieval_service
        self._ttl = ttl
        self._mounts_by_id = {}
        self._mount_id_by_key = {}
        self._mount_ids_by_consumer = {}
        self._mount_ids_in_order = []
        self._lock = RLock()

    def mount(self, artifact_id: str, consumer: str) -> ExecutionArtifactMount:
        """
        Create a temporary mount exposing an artifact to a consumer.

        Raises:
            ExecutionArtifactMountError: If artifact_id or consumer is
                None or blank, the consumer is not permitted to
                retrieve the artifact, or the artifact/consumer pair
                already has an active mount
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(consumer, "consumer")

        try:
            self._execution_artifact_retrieval_service.retrieve(
                ExecutionArtifactRetrievalRequest(artifact_id=artifact_id, consumer=consumer)
            )
        except Exception as error:
            raise ExecutionArtifactMountError(
                f"Cannot mount artifact ID {artifact_id!r} for consumer {consumer!r}: retrieval is not "
                "permitted."
            ) from error

        with self._lock:
            key = (artifact_id, consumer)
            existing_id = self._mount_id_by_key.get(key)

            if existing_id is not None:
                existing = self._mounts_by_id[existing_id]

                if not self._is_expired(existing):
                    raise ExecutionArtifactMountError(
                        f"Artifact ID {artifact_id!r} is already actively mounted for consumer "
                        f"{consumer!r}."
                    )

                self._release(existing_id)

            mount_id = str(uuid4())

            mount = ExecutionArtifactMount(
                mount_id=mount_id,
                artifact_id=artifact_id,
                consumer=consumer,
                path=f"/mnts/{consumer}/{artifact_id}/{mount_id}",
                expires_at=datetime.now(timezone.utc) + self._ttl,
            )

            self._mounts_by_id[mount_id] = mount
            self._mount_id_by_key[key] = mount_id
            self._mount_ids_by_consumer.setdefault(consumer, []).append(mount_id)
            self._mount_ids_in_order.append(mount_id)

            return mount

    def unmount(self, mount_id: str) -> ExecutionArtifactMount:
        """
        Release a mount immediately, whether or not it has expired.

        Raises:
            ExecutionArtifactMountError: If mount_id is None or blank,
                or no mount is known under it
        """

        self._validate_id(mount_id, "mount ID")

        with self._lock:
            if mount_id not in self._mounts_by_id:
                raise ExecutionArtifactMountError(f"No mount is known under mount ID {mount_id!r}.")

            return self._release(mount_id)

    def mounts(self, consumer: str) -> list:
        """
        List a consumer's currently active mounts, in the order they
        were created.

        Raises:
            ExecutionArtifactMountError: If consumer is None or blank
        """

        self._validate_id(consumer, "consumer")

        with self._lock:
            return [
                self._mounts_by_id[mount_id]
                for mount_id in self._mount_ids_by_consumer.get(consumer, [])
                if not self._is_expired(self._mounts_by_id[mount_id])
            ]

    def expired(self) -> list:
        """
        List every currently expired mount that has not yet been
        cleaned up, across all consumers, in the order they were
        created.
        """

        with self._lock:
            return [
                self._mounts_by_id[mount_id]
                for mount_id in self._mount_ids_in_order
                if self._is_expired(self._mounts_by_id[mount_id])
            ]

    def cleanup(self) -> list:
        """
        Release every currently expired mount, freeing their
        artifact/consumer pairs to be mounted again.

        Returns the mounts that were released, in the order they were
        created.
        """

        with self._lock:
            expired_ids = [
                mount_id
                for mount_id in self._mount_ids_in_order
                if self._is_expired(self._mounts_by_id[mount_id])
            ]

            return [self._release(mount_id) for mount_id in expired_ids]

    def _release(self, mount_id: str) -> ExecutionArtifactMount:
        mount = self._mounts_by_id.pop(mount_id)

        key = (mount.artifact_id, mount.consumer)

        if self._mount_id_by_key.get(key) == mount_id:
            del self._mount_id_by_key[key]

        self._mount_ids_by_consumer[mount.consumer].remove(mount_id)
        self._mount_ids_in_order.remove(mount_id)

        return mount

    def _is_expired(self, mount: ExecutionArtifactMount) -> bool:
        return mount.expires_at <= datetime.now(timezone.utc)

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactMountError(f"Cannot use an empty or blank {field_name}.")
