from dataclasses import (
    dataclass,
)

from .execution_artifact_metadata_error import (
    ExecutionArtifactMetadataError,
)


@dataclass(frozen=True)
class ExecutionArtifactTag:
    """
    Immutable record of a single searchable tag attached to an
    execution artifact.

    The tag is a value object only. It performs no persistence of
    its own; applying and looking up tags is the responsibility of
    an execution artifact metadata service.

    Attributes:
        artifact_id: The identifier of the execution artifact this
            tag is attached to
        tag: The tag's text
    """

    artifact_id: str

    tag: str

    def __post_init__(self):
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.tag, "tag")

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactMetadataError(
                f"Cannot build an execution artifact tag with an empty or blank {field_name}."
            )
