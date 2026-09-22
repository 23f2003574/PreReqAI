from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_recovery_guardrails import (
    ACTIVE,
    AgentTaskRecoveryPreflightAuthorizationStore,
    InMemoryAgentTaskRecoveryPreflightAuthorizationStore,
    LLMAgentTaskRecoveryPreflightAuthorizationService,
    LLMAgentTaskRecoveryPreflightStore,
)

from .drift import LLMAgentTaskRecoveryExecutionPreconditionDriftService
from .models import (
    DRIFT_EXECUTION_BLOCKED,
    REVALIDATION_FAILED,
    REVALIDATION_REPLACED,
    REVALIDATION_REUSED,
    AgentTaskRecoveryExecutionPreconditionRevalidationResult,
)
from .service import (
    InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError,
    LLMAgentTaskRecoveryExecutionPreconditionSnapshotService,
)


class InvalidAgentTaskRecoveryExecutionPreconditionRevalidationError(ValueError):
    """Raised when revalidate() is given invalid arguments, or
    snapshot_id names no recorded Commit #1 snapshot for task_id."""


class LLMAgentTaskRecoveryExecutionPreconditionRevalidationService:
    """Rebuilds a Commit #1 execution-precondition snapshot against
    current task/recovery state when Commit #3's own drift classification
    finds it blocking -- never a second snapshot or validation system
    (Rule: "Do not create another snapshot or validation system"):
    revalidate() only ever calls Commit #3's own classify() (itself
    Commit #2's own validate(), itself Commit #1's own get()/compare())
    and, when a rebuild is actually warranted, Commit #1's own capture()
    -- nothing here re-derives policy, dependency, retry-budget, or
    authorization logic a second way.

    Never silently preserves an invalid authorization (Rule): a rebuild
    is only ever attempted against an authorization currently reported
    ACTIVE by backend.agent_task_recovery_guardrails.
    LLMAgentTaskRecoveryPreflightAuthorizationService.get() -- when the
    snapshot's own original authorization is no longer ACTIVE, this class
    looks for an ACTIVE authorization already bound to the task's own
    CURRENT preflight (backend.agent_task_recovery_guardrails.
    LLMAgentTaskRecoveryPreflightStore.get() +
    AgentTaskRecoveryPreflightAuthorizationStore.get_for_preflight()) --
    it never grants, approves, or fabricates a new authorization itself
    (Rule: "Do not execute recovery" -- and neither does it perform the
    separate, human-governed act of authorizing one).

    Fails closed when current state cannot be safely captured (Rule):
    when no ACTIVE authorization exists for the current preflight at all,
    revalidate() reports REVALIDATION_FAILED with new_snapshot_id=None --
    it never fabricates a snapshot bound to a stale or foreign
    authorization, and never treats "could not rebuild" as "still fine to
    execute."

    Idempotent when current state already has an equivalent valid
    snapshot (Rule): before capturing a brand-new snapshot, this class
    checks Commit #1's own latest_for_authorization() for the target
    authorization -- if an already-captured, still-eligible snapshot
    exists (from an earlier revalidate() call, nothing having changed
    since), that one is reused outright rather than minting a redundant
    duplicate every call.

    Never mutates the original snapshot, and preserves complete history
    (Rule): Commit #1's own snapshot store is append-only by construction
    -- old_snapshot_id's own record is only ever read here, never
    rewritten or removed, and the returned result's own old_snapshot_id/
    new_snapshot_id pair is the explicit link between the superseded and
    superseding snapshot.
    """

    def __init__(
        self,
        snapshot_service: LLMAgentTaskRecoveryExecutionPreconditionSnapshotService = None,
        drift_service: LLMAgentTaskRecoveryExecutionPreconditionDriftService = None,
        authorization_service: LLMAgentTaskRecoveryPreflightAuthorizationService = None,
        authorization_store: AgentTaskRecoveryPreflightAuthorizationStore = None,
        preflight_store: LLMAgentTaskRecoveryPreflightStore = None,
    ):
        """
        Args:
            snapshot_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionSnapshotService;
                pass the real instance holding the snapshot capture()
                actually produced, so get()/capture()/
                latest_for_authorization() all see the same history.
            drift_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDriftService;
                pass the real instance wired to the same validation/
                guard/authorization-validation stack.
            authorization_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightAuthorizationService; pass
                the real instance holding a task's actual authorizations.
            authorization_store: Defaults to a fresh
                InMemoryAgentTaskRecoveryPreflightAuthorizationStore; pass
                the same store instance backing authorization_service so
                get_for_preflight() can find a current preflight's
                already-granted authorization.
            preflight_store: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightStore; pass the real
                instance holding a task's actual preflights.
        """
        self._snapshot_service = (
            snapshot_service
            if snapshot_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionSnapshotService()
        )
        self._drift_service = (
            drift_service if drift_service is not None else LLMAgentTaskRecoveryExecutionPreconditionDriftService()
        )
        self._authorization_service = (
            authorization_service
            if authorization_service is not None
            else LLMAgentTaskRecoveryPreflightAuthorizationService()
        )
        self._authorization_store = (
            authorization_store
            if authorization_store is not None
            else InMemoryAgentTaskRecoveryPreflightAuthorizationStore()
        )
        self._preflight_store = preflight_store if preflight_store is not None else LLMAgentTaskRecoveryPreflightStore()

    def revalidate(self, task_id: str, snapshot_id: str) -> AgentTaskRecoveryExecutionPreconditionRevalidationResult:
        """Revalidate task_id's exact Commit #1 snapshot_id, rebuilding it
        against current state if Commit #3's own drift classification
        finds it blocking.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionRevalidationError:
                If task_id/snapshot_id is not a non-empty string, or
                snapshot_id names no recorded snapshot for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")

        if self._snapshot_service.get(task_id, snapshot_id) is None:
            raise InvalidAgentTaskRecoveryExecutionPreconditionRevalidationError(
                f"no snapshot {snapshot_id!r} is recorded for task_id {task_id!r}"
            )

        old_drift = self._drift_service.classify(task_id, snapshot_id)

        if old_drift.category != DRIFT_EXECUTION_BLOCKED:
            return AgentTaskRecoveryExecutionPreconditionRevalidationResult(
                task_id=task_id, old_snapshot_id=snapshot_id, new_snapshot_id=snapshot_id,
                action=REVALIDATION_REUSED, old_drift=old_drift, new_drift=old_drift,
                eligible=old_drift.execution_may_continue, reason=None, revalidated_at=self._now(),
            )

        target_authorization_id = self._resolve_active_authorization(task_id, old_drift.authorization_id)
        if target_authorization_id is None:
            return AgentTaskRecoveryExecutionPreconditionRevalidationResult(
                task_id=task_id, old_snapshot_id=snapshot_id, new_snapshot_id=None,
                action=REVALIDATION_FAILED, old_drift=old_drift, new_drift=None, eligible=False,
                reason="no active authorization exists for the task's current preflight; cannot safely rebuild",
                revalidated_at=self._now(),
            )

        existing = self._snapshot_service.latest_for_authorization(task_id, target_authorization_id)
        if existing is not None and existing.snapshot_id != snapshot_id:
            existing_drift = self._drift_service.classify(task_id, existing.snapshot_id)
            if existing_drift.category != DRIFT_EXECUTION_BLOCKED:
                return AgentTaskRecoveryExecutionPreconditionRevalidationResult(
                    task_id=task_id, old_snapshot_id=snapshot_id, new_snapshot_id=existing.snapshot_id,
                    action=REVALIDATION_REUSED, old_drift=old_drift, new_drift=existing_drift,
                    eligible=existing_drift.execution_may_continue, reason=None, revalidated_at=self._now(),
                )

        try:
            new_snapshot = self._snapshot_service.capture(task_id, target_authorization_id)
        except InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError as error:
            return AgentTaskRecoveryExecutionPreconditionRevalidationResult(
                task_id=task_id, old_snapshot_id=snapshot_id, new_snapshot_id=None,
                action=REVALIDATION_FAILED, old_drift=old_drift, new_drift=None, eligible=False,
                reason=f"current state could not be safely captured: {error}", revalidated_at=self._now(),
            )

        new_drift = self._drift_service.classify(task_id, new_snapshot.snapshot_id)
        action = REVALIDATION_REPLACED if new_drift.execution_may_continue else REVALIDATION_FAILED
        reason = None if new_drift.execution_may_continue else "rebuilt snapshot is still blocked"

        return AgentTaskRecoveryExecutionPreconditionRevalidationResult(
            task_id=task_id, old_snapshot_id=snapshot_id, new_snapshot_id=new_snapshot.snapshot_id,
            action=action, old_drift=old_drift, new_drift=new_drift,
            eligible=new_drift.execution_may_continue, reason=reason, revalidated_at=self._now(),
        )

    def _resolve_active_authorization(self, task_id: str, authorization_id: str) -> Optional[str]:
        authorization = self._authorization_service.get(task_id, authorization_id)
        if authorization is not None and authorization.status == ACTIVE:
            return authorization_id

        current_preflight = self._preflight_store.get(task_id)
        if current_preflight is None:
            return None

        candidate = self._authorization_store.get_for_preflight(task_id, current_preflight.preflight_id)
        if candidate is not None and candidate.status == ACTIVE:
            return candidate.authorization_id
        return None

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionRevalidationError(
                f"{field_name} is required and must be a non-empty string"
            )
