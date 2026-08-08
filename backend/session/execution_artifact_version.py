from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_artifact_version_error import (
    ExecutionArtifactVersionError,
)


@dataclass(frozen=True)
class ExecutionArtifactVersion:
    """
    Immutable snapshot of an execution artifact's contents at a
    single point in time. Creating a new version never overwrites or
    mutates a prior one.

    The version is a value object only. It performs no persistence
    of its own; creating and looking up versions is the
    responsibility of an execution artifact version service.

    Attributes:
        version_id: The version's unique identifier
        artifact_id: The identifier of the execution artifact this
            version belongs to
        version: The version number, starting at 1 for an artifact's
            first version and increasing by 1 for each version after
        location: Where this version's contents can be found, e.g. a
            file path or URL
        created_at: When this version was created
    """

    artifact_id: str

    version: int

    location: str

    version_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.version_id, "version ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.location, "location")

        if not isinstance(self.version, int) or isinstance(self.version, bool):
            raise ExecutionArtifactVersionError(
                "Cannot build an execution artifact version with a non-integer version."
            )

        if self.version < 1:
            raise ExecutionArtifactVersionError(
                "Cannot build an execution artifact version with a version below 1."
            )

        if not isinstance(self.created_at, datetime):
            raise ExecutionArtifactVersionError(
                "Cannot build an execution artifact version with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactVersionError(
                f"Cannot build an execution artifact version with an empty or blank {field_name}."
            )
