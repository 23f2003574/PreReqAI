from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .workspace_execution_artifact_integrity_error import (
    WorkspaceExecutionArtifactIntegrityError,
)

STATUS_VERIFIED = "VERIFIED"

STATUS_CORRUPT = "CORRUPT"

STATUSES = (
    STATUS_VERIFIED,
    STATUS_CORRUPT,
)


@dataclass(frozen=True)
class WorkspaceExecutionArtifactIntegrity:
    """
    Immutable record of a single integrity check performed against an
    execution artifact version, comparing its expected checksum
    against its actual checksum at the moment of the check.

    The record is a value object only. It performs no comparison of
    its own; running and history-tracking checks is the
    responsibility of an execution artifact integrity service.

    Attributes:
        artifact_id: The identifier of the artifact this version
            belongs to
        version_id: The identifier of the version this check was
            performed against
        expected_checksum: The version's recorded checksum baseline
        actual_checksum: The version's checksum as observed at check
            time
        status: VERIFIED if expected_checksum equals actual_checksum,
            otherwise CORRUPT
        check_id: The check's unique identifier
        checked_at: When this check was performed
    """

    artifact_id: str

    version_id: str

    expected_checksum: str

    actual_checksum: str

    status: str

    check_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    checked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.check_id, "check ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.version_id, "version ID")
        self._require_text(self.expected_checksum, "expected checksum")
        self._require_text(self.actual_checksum, "actual checksum")

        expected_status = STATUS_VERIFIED if self.expected_checksum == self.actual_checksum else STATUS_CORRUPT

        if self.status != expected_status:
            raise WorkspaceExecutionArtifactIntegrityError(
                f"Status {self.status!r} does not match the checksum comparison: expected "
                f"{expected_status!r}."
            )

        if not isinstance(self.checked_at, datetime):
            raise WorkspaceExecutionArtifactIntegrityError(
                "Cannot build a workspace execution artifact integrity record with a "
                "non-datetime checked_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactIntegrityError(
                f"Cannot build a workspace execution artifact integrity record with an empty or "
                f"blank {field_name}."
            )
