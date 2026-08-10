from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
)

from uuid import uuid4

from .execution_artifact_cache_error import (
    ExecutionArtifactCacheError,
)


@dataclass(frozen=True)
class ExecutionArtifactCacheEntry:
    """
    Immutable record of a single exact artifact version cached on
    behalf of a consumer, until it expires.

    The entry is a value object only. It performs no caching,
    expiry, or invalidation of its own; putting, retrieving,
    invalidating, and cleaning up entries is the responsibility of an
    execution artifact cache service.

    Attributes:
        cache_id: The entry's unique identifier
        artifact_id: The identifier of the cached artifact
        version: The exact version number cached
        consumer: Who this cached entry was put on behalf of
        expires_at: When this entry stops being a cache hit
    """

    artifact_id: str

    version: int

    consumer: str

    expires_at: datetime

    cache_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.cache_id, "cache ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.consumer, "consumer")

        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ExecutionArtifactCacheError(
                "Cannot build an execution artifact cache entry with a version below 1."
            )

        if not isinstance(self.expires_at, datetime):
            raise ExecutionArtifactCacheError(
                "Cannot build an execution artifact cache entry with a non-datetime expires_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactCacheError(
                f"Cannot build an execution artifact cache entry with an empty or blank {field_name}."
            )
