from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_artifact_cache_entry import (
    ExecutionArtifactCacheEntry,
)

from .execution_artifact_cache_error import (
    ExecutionArtifactCacheError,
)

_DEFAULT_TTL = timedelta(minutes=15)


class ExecutionArtifactCacheService:
    """
    Caches exact versions of retrieved execution artifacts on behalf
    of consumers, so a consumer that already retrieved a version
    through an execution artifact retrieval service does not have to
    repeat that work until the cached entry expires.

    The service's responsibility is cache bookkeeping only. It does
    not retrieve artifacts itself; a caller is expected to retrieve a
    version through the existing retrieval machinery and put() it
    into the cache.

    Behavior:
    - An entry caches one exact artifact version for one consumer; a
      new put() for the same artifact/consumer pair replaces whatever
      was cached before, regardless of version or expiry
    - get() returns None, not an error, for a miss: no entry was ever
      put, or the entry it finds has expired
    - invalidate() removes every cached entry for an artifact, across
      every consumer and whichever version each of them cached
    - Caches are isolated per consumer: entries for one consumer are
      never visible to another

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, ttl: timedelta = _DEFAULT_TTL):
        """
        Args:
            ttl: How long a newly put entry stays a cache hit before
                it expires
        """

        if not isinstance(ttl, timedelta):
            raise ExecutionArtifactCacheError("Cannot use a non-timedelta ttl.")

        self._ttl = ttl
        self._entries_by_id = {}
        self._entry_id_by_key = {}
        self._entry_ids_by_artifact = {}
        self._entry_ids_in_order = []
        self._lock = RLock()

    def put(self, artifact_id: str, version: int, consumer: str) -> ExecutionArtifactCacheEntry:
        """
        Cache an exact artifact version on behalf of a consumer,
        replacing any entry already cached for the same
        artifact/consumer pair.

        Raises:
            ExecutionArtifactCacheError: If artifact_id or consumer is
                None or blank, or version is not a positive integer
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(consumer, "consumer")

        with self._lock:
            key = (artifact_id, consumer)
            existing_id = self._entry_id_by_key.get(key)

            if existing_id is not None:
                self._remove(existing_id)

            cache_id = str(uuid4())

            entry = ExecutionArtifactCacheEntry(
                cache_id=cache_id,
                artifact_id=artifact_id,
                version=version,
                consumer=consumer,
                expires_at=datetime.now(timezone.utc) + self._ttl,
            )

            self._entries_by_id[cache_id] = entry
            self._entry_id_by_key[key] = cache_id
            self._entry_ids_by_artifact.setdefault(artifact_id, []).append(cache_id)
            self._entry_ids_in_order.append(cache_id)

            return entry

    def get(self, artifact_id: str, consumer: str) -> ExecutionArtifactCacheEntry | None:
        """
        Look up a consumer's cached entry for an artifact. Returns
        None for a miss: nothing was ever cached, or the cached entry
        has expired.

        Raises:
            ExecutionArtifactCacheError: If artifact_id or consumer is
                None or blank
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(consumer, "consumer")

        with self._lock:
            entry_id = self._entry_id_by_key.get((artifact_id, consumer))

            if entry_id is None:
                return None

            entry = self._entries_by_id[entry_id]

            if self._is_expired(entry):
                return None

            return entry

    def invalidate(self, artifact_id: str) -> list:
        """
        Remove every cached entry for an artifact, across every
        consumer, regardless of which version each of them cached.

        Raises:
            ExecutionArtifactCacheError: If artifact_id is None or
                blank
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            entry_ids = list(self._entry_ids_by_artifact.get(artifact_id, []))

            return [self._remove(entry_id) for entry_id in entry_ids]

    def expired(self) -> list:
        """
        List every currently expired entry that has not yet been
        cleaned up, across all artifacts and consumers, in the order
        they were put.
        """

        with self._lock:
            return [
                self._entries_by_id[entry_id]
                for entry_id in self._entry_ids_in_order
                if self._is_expired(self._entries_by_id[entry_id])
            ]

    def cleanup(self) -> list:
        """
        Remove every currently expired entry.

        Returns the entries that were removed, in the order they were
        put.
        """

        with self._lock:
            expired_ids = [
                entry_id
                for entry_id in self._entry_ids_in_order
                if self._is_expired(self._entries_by_id[entry_id])
            ]

            return [self._remove(entry_id) for entry_id in expired_ids]

    def _remove(self, entry_id: str) -> ExecutionArtifactCacheEntry:
        entry = self._entries_by_id.pop(entry_id)

        key = (entry.artifact_id, entry.consumer)

        if self._entry_id_by_key.get(key) == entry_id:
            del self._entry_id_by_key[key]

        self._entry_ids_by_artifact[entry.artifact_id].remove(entry_id)
        self._entry_ids_in_order.remove(entry_id)

        return entry

    def _is_expired(self, entry: ExecutionArtifactCacheEntry) -> bool:
        return entry.expires_at <= datetime.now(timezone.utc)

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactCacheError(f"Cannot use an empty or blank {field_name}.")
