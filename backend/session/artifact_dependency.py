from dataclasses import (
    dataclass,
    field,
)

from typing import Optional
from uuid import uuid4

from .execution_artifact_dependency_error import (
    ExecutionArtifactDependencyError,
)


@dataclass(frozen=True)
class ArtifactDependency:
    """
    Immutable record that one execution artifact requires another as
    an input, optionally pinned to an exact version.

    The dependency is a value object only. It performs no validation
    of whether the requirement is currently met; adding, removing,
    and validating dependencies is the responsibility of an execution
    artifact dependency service.

    Attributes:
        dependency_id: The dependency's unique identifier
        artifact_id: The identifier of the artifact that has the
            requirement
        required_artifact_id: The identifier of the artifact it
            requires
        required_version: The exact version number required, or None
            if any available version satisfies the dependency
    """

    artifact_id: str

    required_artifact_id: str

    required_version: Optional[int] = None

    dependency_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.dependency_id, "dependency ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.required_artifact_id, "required artifact ID")

        if self.artifact_id == self.required_artifact_id:
            raise ExecutionArtifactDependencyError(
                f"Artifact ID {self.artifact_id!r} cannot depend on itself."
            )

        if self.required_version is not None:
            if not isinstance(self.required_version, int) or isinstance(self.required_version, bool):
                raise ExecutionArtifactDependencyError(
                    "Cannot build an artifact dependency with a non-integer required_version."
                )

            if self.required_version < 1:
                raise ExecutionArtifactDependencyError(
                    "Cannot build an artifact dependency with a required_version below 1."
                )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDependencyError(
                f"Cannot build an artifact dependency with an empty or blank {field_name}."
            )
