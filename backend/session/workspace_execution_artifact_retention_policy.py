from dataclasses import (
    dataclass,
    field,
)

from numbers import (
    Real,
)

from uuid import uuid4

from .workspace_execution_artifact_retention_error import (
    WorkspaceExecutionArtifactRetentionError,
)


@dataclass(frozen=True)
class WorkspaceExecutionArtifactRetentionPolicy:
    """
    Immutable snapshot of how long an artifact's versions remain
    eligible for storage and retrieval before they become
    GC-eligible.

    The policy is a value object only. It performs no evaluation of
    its own; configuring, evaluating, and disabling policies is the
    responsibility of an execution artifact retention service, which
    produces a new snapshot for every transition rather than mutating
    an existing one.

    Attributes:
        artifact_id: The identifier of the artifact this policy
            governs
        retention_seconds: How long, in seconds, a version remains
            eligible after it is created; must be a positive number
        enabled: Whether this policy is currently enforced; a
            disabled policy never causes automatic expiration
        policy_id: The policy's unique identifier
    """

    artifact_id: str

    retention_seconds: float

    enabled: bool = True

    policy_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.artifact_id, "artifact ID")

        if (
            self.retention_seconds is None
            or isinstance(self.retention_seconds, bool)
            or not isinstance(self.retention_seconds, Real)
            or self.retention_seconds <= 0
        ):
            raise WorkspaceExecutionArtifactRetentionError(
                f"Cannot build a workspace execution artifact retention policy with a "
                f"non-positive retention_seconds: {self.retention_seconds!r}."
            )

        if not isinstance(self.enabled, bool):
            raise WorkspaceExecutionArtifactRetentionError(
                "Cannot build a workspace execution artifact retention policy with a non-bool "
                "enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactRetentionError(
                f"Cannot build a workspace execution artifact retention policy with an empty or "
                f"blank {field_name}."
            )
