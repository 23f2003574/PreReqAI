from datetime import datetime, timezone

from .models import AgentTaskRecoveryPreflightDependencySnapshotTrustChangeResult
from .trust import LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService
from .trust_history import LLMAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryService

# Field-value comparison only (Rule: "Do not infer trust changes from
# timestamps alone") -- checked_at/verified_at/recorded_at never appear
# here, on purpose.
_COMPARED_DIMENSIONS = ("trusted", "integrity_status", "signature_status", "version", "preflight_id", "blocking_reasons")


class InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustChangeError(ValueError):
    """Raised when check()/has_changed() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService:
    """Detects when a previously trusted Commit #1 snapshot has become
    untrustworthy since Commit #7's own last recorded verification --
    never a second verification implementation (Rule: "Do not duplicate
    verification logic"): check() only ever calls Commit #6's own
    validate() for the CURRENT state and Commit #7's own latest() for the
    PREVIOUS state; nothing here recomputes a hash, an HMAC, a version
    number, or a supersession check itself.

    Every one of integrity/signature/version-identity/supersession
    change is caught by the SAME plain field-value diff (Rule): Commit
    #6's own validate() already folds corruption, invalid/missing
    signatures, and supersession into its own integrity_status/
    signature_status/blocking_reasons -- a change in ANY of those, or in
    version/preflight_id, is exactly a change in one of this service's
    own compared dimensions. No dimension is independently re-derived.

    Never rewrites history (Rule): this class only ever READS through
    Commit #7's own latest() -- it holds no reference to anything that
    could write to that store, and Commit #6's own validate() call
    appends (never rewrites) via whatever history_service IT was
    constructed with, entirely outside this class's control.

    Read-only, no recovery/scheduling mutation (Rule); deterministic
    (Rule): a pure comparison of two already-computed, already-
    deterministic structured results.
    """

    def __init__(
        self,
        trust_service: LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService = None,
        history_service: LLMAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryService = None,
    ):
        self._trust_service = (
            trust_service if trust_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotTrustService()
        )
        self._history_service = (
            history_service
            if history_service is not None
            else LLMAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryService()
        )

    def has_changed(self, task_id: str, snapshot_id: str) -> bool:
        """Shorthand for check(task_id, snapshot_id).changed."""
        return self.check(task_id, snapshot_id).changed

    def check(self, task_id: str, snapshot_id: str) -> AgentTaskRecoveryPreflightDependencySnapshotTrustChangeResult:
        """Compare task_id/snapshot_id's previously recorded trust state
        against a freshly computed one, right now.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustChangeError:
                If task_id or snapshot_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")

        previous = self._history_service.latest(task_id, snapshot_id)
        current = self._trust_service.validate(task_id, snapshot_id)  # Rule: "fresh validation through the existing trust service"

        if previous is None:
            return AgentTaskRecoveryPreflightDependencySnapshotTrustChangeResult(
                task_id=task_id, snapshot_id=snapshot_id, previous_trust=None, current_trust=current,
                changed=False, changed_dimensions=(), evidence=(), revalidation_required=True,
                checked_at=self._now(),
            )

        dimensions = []
        evidence = []
        for name in _COMPARED_DIMENSIONS:
            previous_value = getattr(previous, name)
            current_value = getattr(current, name)
            if previous_value != current_value:
                dimensions.append(name)
                evidence.append(f"{name} changed from {previous_value!r} to {current_value!r}")

        return AgentTaskRecoveryPreflightDependencySnapshotTrustChangeResult(
            task_id=task_id, snapshot_id=snapshot_id, previous_trust=previous, current_trust=current,
            changed=bool(dimensions), changed_dimensions=tuple(dimensions), evidence=tuple(evidence),
            revalidation_required=not current.trusted, checked_at=self._now(),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustChangeError(
                f"{field_name} is required and must be a non-empty string"
            )
