from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_artifact_decision_error import (
    ExecutionArtifactDecisionError,
)

ACTION_PUBLISH = "PUBLISH"

ACTION_PROMOTE = "PROMOTE"

ACTION_DISTRIBUTE = "DISTRIBUTE"

ACTION_RELEASE = "RELEASE"

ACTION_RETIRE = "RETIRE"

ACTIONS = (
    ACTION_PUBLISH,
    ACTION_PROMOTE,
    ACTION_DISTRIBUTE,
    ACTION_RELEASE,
    ACTION_RETIRE,
)


@dataclass(frozen=True)
class ExecutionArtifactDecision:
    """
    Immutable record of a single lifecycle action attempted against
    an artifact version by the orchestration pipeline, and whether it
    was allowed.

    The decision is a value object only. It performs no evaluation of
    its own; deciding and recording lifecycle actions is the
    responsibility of an execution artifact orchestration service.

    Attributes:
        artifact_id: The identifier of the artifact the action was
            attempted against
        version_id: The identifier of the version the action was
            attempted against
        action: Which lifecycle action was attempted, one of ACTIONS
        allowed: Whether the action was permitted and carried out
        reason: Why the action was allowed or blocked
        decision_id: The decision's unique identifier
        created_at: When this decision was recorded
    """

    artifact_id: str

    version_id: str

    action: str

    allowed: bool

    reason: str

    decision_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.decision_id, "decision ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.version_id, "version ID")
        self._require_text(self.reason, "reason")

        if self.action not in ACTIONS:
            raise ExecutionArtifactDecisionError(
                f"Cannot build an execution artifact decision with an unknown action: "
                f"{self.action!r}."
            )

        if not isinstance(self.allowed, bool):
            raise ExecutionArtifactDecisionError(
                "Cannot build an execution artifact decision with a non-bool allowed."
            )

        if not isinstance(self.created_at, datetime):
            raise ExecutionArtifactDecisionError(
                "Cannot build an execution artifact decision with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDecisionError(
                f"Cannot build an execution artifact decision with an empty or blank {field_name}."
            )
