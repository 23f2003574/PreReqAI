from dataclasses import (
    dataclass,
)

from typing import Any

from .execution_artifact_metadata_error import (
    ExecutionArtifactMetadataError,
)


@dataclass(frozen=True)
class ExecutionArtifactMetadata:
    """
    Immutable record of a single searchable key/value entry attached
    to an execution artifact.

    The metadata entry is a value object only. It performs no
    persistence of its own; setting, retrieving, and removing
    metadata entries is the responsibility of an execution artifact
    metadata service.

    Attributes:
        artifact_id: The identifier of the execution artifact this
            entry is attached to
        key: The metadata field name
        value: The metadata field's current value
    """

    artifact_id: str

    key: str

    value: Any

    def __post_init__(self):
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.key, "key")

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactMetadataError(
                f"Cannot build execution artifact metadata with an empty or blank {field_name}."
            )
