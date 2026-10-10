from dataclasses import (
    dataclass,
)

from .execution_artifact_access_error import (
    ExecutionArtifactAccessError,
)

SUPPORTED_OPERATIONS = frozenset(
    {
        "READ",
        "PROMOTE",
        "DELETE",
    }
)


@dataclass(frozen=True)
class ArtifactPermission:
    """
    Immutable record granting a principal the ability to perform one
    operation against an execution artifact, and, by inheritance,
    every version of it.

    The permission is a value object only. It performs no
    authorization of its own; granting, revoking, and checking
    permissions is the responsibility of an execution artifact access
    service.

    Attributes:
        artifact_id: The identifier of the execution artifact this
            grant applies to
        principal: Who or what the grant applies to
        operation: The operation the grant allows, one of READ,
            PROMOTE, or DELETE
    """

    artifact_id: str

    principal: str

    operation: str

    def __post_init__(self):
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.principal, "principal")
        self._require_text(self.operation, "operation")

        if self.operation not in SUPPORTED_OPERATIONS:
            raise ExecutionArtifactAccessError(
                f"Unsupported operation {self.operation!r}: expected one of {sorted(SUPPORTED_OPERATIONS)}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactAccessError(
                f"Cannot build an artifact permission with an empty or blank {field_name}."
            )
