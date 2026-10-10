from dataclasses import (
    dataclass,
    field,
)

from .execution_artifact_version import (
    ExecutionArtifactVersion,
)

from .execution_artifact_retention_error import (
    ExecutionArtifactRetentionError,
)


@dataclass(frozen=True)
class ExecutionArtifactRetentionResult:
    """
    Immutable outcome of evaluating a retention policy against an
    artifact's version history.

    Attributes:
        removed: The versions that fall outside the policy's limits,
            oldest first
        retained: The versions that remain within the policy's
            limits, oldest first
    """

    removed: tuple = field(default_factory=tuple)

    retained: tuple = field(default_factory=tuple)

    def __post_init__(self):
        object.__setattr__(self, "removed", self._require_versions(self.removed, "removed"))
        object.__setattr__(self, "retained", self._require_versions(self.retained, "retained"))

    @staticmethod
    def _require_versions(value, field_name: str) -> tuple:
        if value is None:
            raise ExecutionArtifactRetentionError(
                f"Cannot build a retention result with a None {field_name}."
            )

        versions = tuple(value)

        for entry in versions:
            if not isinstance(entry, ExecutionArtifactVersion):
                raise ExecutionArtifactRetentionError(
                    f"Cannot build a retention result with a non-ExecutionArtifactVersion in {field_name}."
                )

        return versions
