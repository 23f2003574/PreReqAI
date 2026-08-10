from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_artifact_prefetch_error import (
    ExecutionArtifactPrefetchError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "PENDING",
        "SKIPPED",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    }
)


@dataclass(frozen=True)
class ExecutionArtifactPrefetch:
    """
    Immutable record of a request to prefetch an execution artifact
    on behalf of a consumer before it is actually needed.

    The prefetch is a value object only. It performs no retrieval or
    caching of its own; scheduling, executing, cancelling, and
    looking up prefetches is the responsibility of an execution
    artifact prefetch service.

    Attributes:
        prefetch_id: The prefetch's unique identifier
        artifact_id: The identifier of the artifact to prefetch
        consumer: Who this prefetch is being performed on behalf of
        scheduled_at: When this prefetch was scheduled
        status: The prefetch's current status, one of PENDING,
            SKIPPED, SUCCEEDED, FAILED, or CANCELLED
    """

    artifact_id: str

    consumer: str

    prefetch_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    scheduled_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    status: str = "PENDING"

    def __post_init__(self):
        self._require_text(self.prefetch_id, "prefetch ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.consumer, "consumer")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionArtifactPrefetchError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if not isinstance(self.scheduled_at, datetime):
            raise ExecutionArtifactPrefetchError(
                "Cannot build an execution artifact prefetch with a non-datetime scheduled_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactPrefetchError(
                f"Cannot build an execution artifact prefetch with an empty or blank {field_name}."
            )
