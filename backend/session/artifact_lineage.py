from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_artifact_lineage_error import (
    ExecutionArtifactLineageError,
)


@dataclass(frozen=True)
class ArtifactLineage:
    """
    Immutable record of how a single execution artifact version was
    produced: from which input versions, during which execution
    session.

    The lineage record is a value object only. It performs no
    validation of whether the referenced versions exist; recording
    and looking up lineage is the responsibility of an execution
    artifact lineage service.

    Attributes:
        lineage_id: The record's unique identifier
        output_version_id: The identifier of the version this record
            describes the origin of
        input_version_ids: The identifiers of the versions consumed
            to produce output_version_id, in the order they were
            given
        session_id: The identifier of the execution session during
            which output_version_id was produced
        created_at: When this lineage record was created
    """

    output_version_id: str

    input_version_ids: tuple

    session_id: str

    lineage_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.lineage_id, "lineage ID")
        self._require_text(self.output_version_id, "output version ID")
        self._require_text(self.session_id, "session ID")

        if self.input_version_ids is None:
            raise ExecutionArtifactLineageError(
                "Cannot build an artifact lineage record with None input_version_ids."
            )

        input_version_ids = tuple(self.input_version_ids)

        for input_version_id in input_version_ids:
            self._require_text(input_version_id, "input version ID")

        if self.output_version_id in input_version_ids:
            raise ExecutionArtifactLineageError(
                f"Version ID {self.output_version_id!r} cannot be listed as its own input."
            )

        object.__setattr__(self, "input_version_ids", input_version_ids)

        if not isinstance(self.created_at, datetime):
            raise ExecutionArtifactLineageError(
                "Cannot build an artifact lineage record with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactLineageError(
                f"Cannot build an artifact lineage record with an empty or blank {field_name}."
            )
