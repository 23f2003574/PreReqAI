from dataclasses import (
    dataclass,
    field,
)

from uuid import uuid4

from .execution_artifact_distribution_access_error import (
    ExecutionArtifactDistributionAccessError,
)

SUPPORTED_OPERATIONS = frozenset(
    {
        "READ",
        "PUBLISH",
    }
)


@dataclass(frozen=True)
class ArtifactDistributionPermission:
    """
    Immutable record granting a distribution channel the ability to
    perform one operation against artifacts of a given type.

    The permission is a value object only. It performs no
    authorization of its own; granting, revoking, and checking
    permissions is the responsibility of an execution artifact
    distribution access service.

    Attributes:
        channel_id: The identifier of the distribution channel this
            grant applies to
        artifact_type: The kind of artifact this grant applies to,
            e.g. "log" or "report"
        operation: The operation the grant allows, READ or PUBLISH
        permission_id: The permission's unique identifier
    """

    channel_id: str

    artifact_type: str

    operation: str

    permission_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.channel_id, "channel ID")
        self._require_text(self.artifact_type, "artifact type")
        self._require_text(self.operation, "operation")
        self._require_text(self.permission_id, "permission ID")

        if self.operation not in SUPPORTED_OPERATIONS:
            raise ExecutionArtifactDistributionAccessError(
                f"Unsupported operation {self.operation!r}: expected one of {sorted(SUPPORTED_OPERATIONS)}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionAccessError(
                f"Cannot build a distribution permission with an empty or blank {field_name}."
            )
