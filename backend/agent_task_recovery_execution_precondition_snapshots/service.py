from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService, UnknownAgentTaskError
from backend.agent_task_queue_retry_eligibility import LLMAgentTaskQueueRetryEligibilityService
from backend.agent_task_readiness import LLMAgentTaskReadinessService
from backend.agent_task_recovery_guardrails import (
    ACTIVE,
    LLMAgentTaskRecoveryPreflightAuthorizationService,
    LLMAgentTaskRecoveryPreflightStore,
)

from .models import (
    AgentTaskRecoveryExecutionPreconditionFieldChange,
    AgentTaskRecoveryExecutionPreconditionSnapshot,
    AgentTaskRecoveryExecutionPreconditionSnapshotDiff,
)
from .store import (
    AgentTaskRecoveryExecutionPreconditionSnapshotStore,
    InMemoryAgentTaskRecoveryExecutionPreconditionSnapshotStore,
)


class InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError(ValueError):
    """Raised when capture()/get()/compare() is given invalid arguments,
    when capture() is given an authorization_id that is not recorded for
    task_id (or is recorded but no longer ACTIVE), or when compare()
    names a snapshot_id that does not exist for task_id."""


class LLMAgentTaskRecoveryExecutionPreconditionSnapshotService:
    """Captures the exact task/recovery state immediately before an
    authorized recovery execution, so post-execution analysis has a
    reliable baseline to compare against -- a distinct boundary from
    backend.agent_task_recovery_preflight_dependency_snapshots (that
    package captures the dependency graph a SCHEDULE was prepared
    against, before execution was ever authorized; this one captures
    what was actually true the instant an already-ACTIVE authorization
    was about to be handed to backend.agent_task_event_analytics.
    LLMAgentTaskFailureRecoveryService.execute_plan()).

    Reuses every existing model this state already lives in (Rule: "Do
    not invent another snapshot framework if an existing one can support
    this"): authorization identity/version comes from backend.
    agent_task_recovery_guardrails' own AgentTaskRecoveryPreflightAuthorization;
    the authorized recovery plan comes from that same authorization's
    own bound preflight, read through backend.agent_task_recovery_guardrails'
    own LLMAgentTaskRecoveryPreflightStore; task lifecycle/retry/
    dependency-readiness/policy state come from whichever of
    backend.agent_task_lifecycle.LLMAgentTaskLifecycleService,
    backend.agent_task_queue_retry_eligibility.
    LLMAgentTaskQueueRetryEligibilityService, and backend.
    agent_task_readiness.LLMAgentTaskReadinessService were supplied --
    nothing here re-derives any of their answers a second way.

    Bound to the exact (task_id, authorization_id) (Rule: "Bind snapshot
    to the exact authorization and recovery plan"): capture() reads
    backend.agent_task_recovery_guardrails' own authorization record for
    that exact authorization_id and refuses to proceed unless it exists,
    belongs to task_id, and is still ACTIVE -- a missing, foreign, or
    REVOKED authorization can never anchor a "this execution was
    authorized" baseline.

    Every optional collaborator is duck-typed, used only if given (the
    same shape backend.agent_task_recovery_preflight_dependency_snapshots'
    own snapshot service already establishes for its own optional
    dependency_resolver/dependency_service): omitting one simply means
    the state it would have captured is None, never fabricated (Rule:
    "Capture only state actually available in the repository"). A fresh,
    default-constructed authorization_service/preflight_store (like every
    other optional-collaborator default in this project) means capture()
    will find no authorization/preflight until the caller wires the SAME
    instances that actually recorded them -- the same "always wire the
    real one from the stack" sharp edge backend.
    agent_task_recovery_preflight_dependency_snapshots' own service
    already documents for itself.

    Immutable after creation (Rule): AgentTaskRecoveryExecutionPrecondition
    Snapshot is a frozen dataclass, and the underlying store this class
    writes through has no update()/delete() at all -- once captured, a
    snapshot is never rewritten, only ever read back by get() or compared
    against by compare().

    Never executes, authorizes, schedules, or mutates recovery (Rule):
    capture()/get()/compare() only ever call read-only methods
    (get()/check()) on their collaborators and save()/get() on their own
    store -- nothing here calls execute()/execute_plan()/authorize()/
    schedule_retry() or any other write path anywhere else in this
    repository. Integrate capture() by calling it with the exact
    authorization_id immediately before handing that authorization's own
    bound recovery plan to LLMAgentTaskFailureRecoveryService.execute_plan().
    """

    def __init__(
        self,
        authorization_service: LLMAgentTaskRecoveryPreflightAuthorizationService = None,
        preflight_store: LLMAgentTaskRecoveryPreflightStore = None,
        lifecycle_service: LLMAgentTaskLifecycleService = None,
        retry_eligibility_service: LLMAgentTaskQueueRetryEligibilityService = None,
        readiness_service: LLMAgentTaskReadinessService = None,
        store: AgentTaskRecoveryExecutionPreconditionSnapshotStore = None,
    ):
        """
        Args:
            authorization_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightAuthorizationService; pass
                the real instance holding a task's actual authorizations
                for capture()/compare() to ever find one.
            preflight_store: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightStore; pass the real
                instance holding a task's actual preflights so
                capture() can resolve the authorized recovery plan.
            lifecycle_service: No default; enables task_state capture.
            retry_eligibility_service: No default; enables
                retry_eligibility capture.
            readiness_service: No default; enables readiness capture
                (dependency readiness and applicable policy state).
            store: Defaults to a fresh
                InMemoryAgentTaskRecoveryExecutionPreconditionSnapshotStore.
        """
        self._authorization_service = (
            authorization_service
            if authorization_service is not None
            else LLMAgentTaskRecoveryPreflightAuthorizationService()
        )
        self._preflight_store = preflight_store if preflight_store is not None else LLMAgentTaskRecoveryPreflightStore()
        self._lifecycle_service = lifecycle_service
        self._retry_eligibility_service = retry_eligibility_service
        self._readiness_service = readiness_service
        self._store = store if store is not None else InMemoryAgentTaskRecoveryExecutionPreconditionSnapshotStore()

    def capture(self, task_id: str, authorization_id: str) -> AgentTaskRecoveryExecutionPreconditionSnapshot:
        """Capture task_id's current state, bound to the exact,
        currently-ACTIVE authorization_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError: If
                task_id/authorization_id is not a non-empty string, no
                authorization authorization_id is recorded for task_id,
                or that authorization is not currently ACTIVE
        """
        self._require_text(task_id, "task_id")
        self._require_text(authorization_id, "authorization_id")

        authorization = self._authorization_service.get(task_id, authorization_id)
        if authorization is None:
            raise InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError(
                f"no authorization {authorization_id!r} is recorded for task_id {task_id!r}"
            )
        if authorization.status != ACTIVE:
            raise InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError(
                f"authorization {authorization_id!r} is not active (status={authorization.status!r}) "
                "and cannot anchor an execution precondition snapshot"
            )

        preflight = next(
            (
                record
                for record in self._preflight_store.history(task_id)
                if record.preflight_id == authorization.preflight_id
            ),
            None,
        )
        recovery_plan = preflight.plan if preflight is not None else None

        snapshot = AgentTaskRecoveryExecutionPreconditionSnapshot(
            task_id=task_id,
            authorization_id=authorization_id,
            preflight_id=authorization.preflight_id,
            approval_id=authorization.approval_id,
            authorization_status=authorization.status,
            task_state=self._task_state(task_id),
            recovery_plan=recovery_plan,
            retry_eligibility=self._retry_eligibility(task_id),
            readiness=self._readiness(task_id),
            captured_at=self._now(),
        )
        return self._store.save(snapshot)

    def get(self, task_id: str, snapshot_id: str) -> Optional[AgentTaskRecoveryExecutionPreconditionSnapshot]:
        """task_id's exact snapshot_id -- None if it does not exist or
        belongs to a different task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError: If
                task_id or snapshot_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")

        record = self._store.get(snapshot_id)
        if record is None or record.task_id != task_id:
            return None
        return record

    def latest_for_authorization(
        self, task_id: str, authorization_id: str
    ) -> Optional[AgentTaskRecoveryExecutionPreconditionSnapshot]:
        """The most recently captured snapshot bound to task_id's exact
        authorization_id -- None if none exists. A pure read of the
        existing store's own list_for_task(); never captures anything.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError: If
                task_id or authorization_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(authorization_id, "authorization_id")

        matching = [
            record for record in self._store.list_for_task(task_id) if record.authorization_id == authorization_id
        ]
        return matching[-1] if matching else None

    def compare(self, task_id: str, snapshot_id: str) -> AgentTaskRecoveryExecutionPreconditionSnapshotDiff:
        """Compare task_id's exact, already-persisted snapshot_id against
        task_id's CURRENT state, right now. Read-only: never mutates the
        snapshot or any authorization/recovery state.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError: If
                task_id/snapshot_id is not a non-empty string, or names
                no recorded snapshot for task_id
        """
        snapshot = self.get(task_id, snapshot_id)
        if snapshot is None:
            raise InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError(
                f"no snapshot {snapshot_id!r} is recorded for task_id {task_id!r}"
            )

        current_authorization = self._authorization_service.get(task_id, snapshot.authorization_id)
        current_authorization_status = current_authorization.status if current_authorization is not None else None
        current_task_state = self._task_state(task_id)
        current_retry_eligibility = self._retry_eligibility(task_id)
        current_readiness = self._readiness(task_id)

        changes = []

        authorization_status_changed = current_authorization_status != snapshot.authorization_status
        if authorization_status_changed:
            changes.append(
                AgentTaskRecoveryExecutionPreconditionFieldChange(
                    field="authorization_status",
                    previous_value=snapshot.authorization_status,
                    current_value=current_authorization_status,
                )
            )

        task_state_changed = current_task_state != snapshot.task_state
        if task_state_changed:
            changes.append(
                AgentTaskRecoveryExecutionPreconditionFieldChange(
                    field="task_state", previous_value=snapshot.task_state, current_value=current_task_state
                )
            )

        retry_eligibility_changed = current_retry_eligibility != snapshot.retry_eligibility
        if retry_eligibility_changed:
            changes.append(
                AgentTaskRecoveryExecutionPreconditionFieldChange(
                    field="retry_eligibility",
                    previous_value=snapshot.retry_eligibility,
                    current_value=current_retry_eligibility,
                )
            )

        readiness_changed = current_readiness != snapshot.readiness
        if readiness_changed:
            changes.append(
                AgentTaskRecoveryExecutionPreconditionFieldChange(
                    field="readiness", previous_value=snapshot.readiness, current_value=current_readiness
                )
            )

        return AgentTaskRecoveryExecutionPreconditionSnapshotDiff(
            task_id=task_id,
            snapshot_id=snapshot_id,
            authorization_id=snapshot.authorization_id,
            preflight_id=snapshot.preflight_id,
            changed=bool(changes),
            authorization_status_changed=authorization_status_changed,
            task_state_changed=task_state_changed,
            retry_eligibility_changed=retry_eligibility_changed,
            readiness_changed=readiness_changed,
            changes=tuple(changes),
            current_authorization_status=current_authorization_status,
            current_task_state=current_task_state,
            current_retry_eligibility=current_retry_eligibility,
            current_readiness=current_readiness,
            compared_at=self._now(),
        )

    def _task_state(self, task_id: str) -> Optional[str]:
        if self._lifecycle_service is None:
            return None
        try:
            return self._lifecycle_service.get(task_id).current_state
        except UnknownAgentTaskError:
            return None

    def _retry_eligibility(self, task_id: str):
        if self._retry_eligibility_service is None:
            return None
        return self._retry_eligibility_service.check(task_id)

    def _readiness(self, task_id: str):
        if self._readiness_service is None:
            return None
        return self._readiness_service.check(task_id)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionSnapshotError(
                f"{field_name} is required and must be a non-empty string"
            )
