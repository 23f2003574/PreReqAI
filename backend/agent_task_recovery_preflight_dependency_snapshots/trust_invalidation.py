from datetime import datetime, timezone

from backend.agent_task_recovery_guardrails import LLMAgentTaskRecoveryPreflightInvalidationService, LLMAgentTaskRecoveryPreflightStore

from .models import AgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationResult
from .service import LLMAgentTaskRecoveryPreflightDependencySnapshotService
from .trust_change import LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService


class InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationError(ValueError):
    """Raised when check()/invalidate() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationService:
    """Automatically invalidates a snapshot's referencing preflight once
    it loses trust, so stale trusted state cannot keep feeding recovery
    decisions -- never a second invalidation framework (Rule: "Do not
    create another invalidation framework"): the actual invalidation
    write is always backend.agent_task_recovery_guardrails' own
    LLMAgentTaskRecoveryPreflightInvalidationService.invalidate(),
    delegated verbatim; the trust verdict driving it is always Commit
    #8's own LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService.
    check() (a FRESH call every time, Rule: "Freshly evaluate trust
    through the existing trust-change service") -- nothing here
    recomputes integrity, signature, or trust logic itself.

    Invalidates only on a genuine failure (Rule): warranted is exactly
    `not change.current_trust.trusted` -- a still-trusted snapshot is
    never invalidated, whether or not something merely changed.

    Bound to the exact preflight (Rule: correctness, not explicitly
    named but load-bearing): Commit #4-of-agent_task_recovery_guardrails'
    own invalidate(task_id, reason) always acts on task_id's CURRENT
    preflight -- calling it blindly would invalidate the WRONG preflight
    if this snapshot's own preflight_id has since been superseded. This
    class checks preflight_store.get(task_id).preflight_id ==
    snapshot.preflight_id first; only then delegates to invalidate().
    When the snapshot's preflight is no longer current at all, nothing
    live needs invalidating -- it is already non-actionable by
    construction (a superseded preflight was never eligible for fresh
    scheduling in the first place), so this is reported as already
    effectively invalidated without a redundant write.

    Idempotent (Rule): invalidate() delegates to a service that is
    ALREADY idempotent by construction (repeated calls for an
    already-invalidated preflight return that same original record,
    never re-invalidating) -- no separate idempotency bookkeeping is
    added here.

    Never mutates the original snapshot or its trust history (Rule):
    this class holds no reference to Commit #1's own snapshot store or
    Commit #7's own history store's write paths; check() never writes
    anything at all. Never executes, reschedules, or authorizes recovery
    (Rule): no such collaborator is held.
    """

    def __init__(
        self,
        snapshot_service: LLMAgentTaskRecoveryPreflightDependencySnapshotService = None,
        trust_change_service: LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService = None,
        preflight_store: LLMAgentTaskRecoveryPreflightStore = None,
        preflight_invalidation_service: LLMAgentTaskRecoveryPreflightInvalidationService = None,
        scheduling_service=None,
    ):
        """
        Args:
            scheduling_service: Optional backend.agent_task_recovery_scheduling.
                LLMAgentTaskRecoveryPreflightSchedulingService (duck-
                typed, only list() is called) -- enables
                affected_schedule_ids; () without it, never fabricated.
        """
        self._snapshot_service = (
            snapshot_service if snapshot_service is not None else LLMAgentTaskRecoveryPreflightDependencySnapshotService()
        )
        self._trust_change_service = (
            trust_change_service
            if trust_change_service is not None
            else LLMAgentTaskRecoveryPreflightDependencySnapshotTrustChangeService()
        )
        self._preflight_store = preflight_store if preflight_store is not None else LLMAgentTaskRecoveryPreflightStore()
        self._preflight_invalidation_service = (
            preflight_invalidation_service
            if preflight_invalidation_service is not None
            else LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=self._preflight_store)
        )
        self._scheduling_service = scheduling_service

    def check(self, task_id: str, snapshot_id: str) -> AgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationResult:
        """Read-only dry run: would task_id's exact snapshot_id warrant
        invalidation right now -- never writes anything.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationError:
                If task_id or snapshot_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")
        return self._process(task_id, snapshot_id, None, perform=False)

    def invalidate(
        self, task_id: str, snapshot_id: str, reason: str = None
    ) -> AgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationResult:
        """Invalidate task_id's exact snapshot_id's referencing preflight
        if, and only if, a fresh trust check finds it genuinely warranted.
        Idempotent: an already-invalidated preflight is reported
        unchanged, never re-invalidated.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationError:
                If task_id or snapshot_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")
        return self._process(task_id, snapshot_id, reason, perform=True)

    def _process(self, task_id, snapshot_id, reason, perform):
        now = self._now()
        snapshot = self._snapshot_service.get(task_id, snapshot_id)
        if snapshot is None:
            return AgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationResult(
                task_id=task_id, snapshot_id=snapshot_id, preflight_id=None, warranted=False, invalidated=False,
                reason=None, affected_preflight_ids=(), affected_schedule_ids=(),
                evidence=("no snapshot is recorded for this task_id/snapshot_id",), checked_at=now,
            )

        change = self._trust_change_service.check(task_id, snapshot_id)
        warranted = not change.current_trust.trusted
        evidence = change.evidence if change.evidence else tuple(change.current_trust.blocking_reasons)

        affected_preflight_ids = (snapshot.preflight_id,) if snapshot.preflight_id else ()
        affected_schedule_ids = ()
        if self._scheduling_service is not None and snapshot.preflight_id:
            affected_schedule_ids = tuple(
                schedule.schedule_id
                for schedule in self._scheduling_service.list(task_id)
                if schedule.preflight_id == snapshot.preflight_id
            )

        if not warranted:
            return AgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationResult(
                task_id=task_id, snapshot_id=snapshot_id, preflight_id=snapshot.preflight_id,
                warranted=False, invalidated=False, reason=None,
                affected_preflight_ids=affected_preflight_ids, affected_schedule_ids=affected_schedule_ids,
                evidence=evidence, checked_at=now,
            )

        default_reason = (
            f"dependency snapshot {snapshot_id!r} lost trust: {'; '.join(change.current_trust.blocking_reasons) or 'no reason given'}"
        )
        final_reason = reason or default_reason

        already = self._preflight_invalidation_service.get_invalidation(snapshot.preflight_id) if snapshot.preflight_id else None
        current_preflight = self._preflight_store.get(task_id)
        is_current = (
            snapshot.preflight_id is not None
            and current_preflight is not None
            and current_preflight.preflight_id == snapshot.preflight_id
        )

        if not perform:
            recorded_reason = already.reason if already is not None else (final_reason if is_current else None)
            return AgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationResult(
                task_id=task_id, snapshot_id=snapshot_id, preflight_id=snapshot.preflight_id,
                warranted=True, invalidated=already is not None or not is_current, reason=recorded_reason,
                affected_preflight_ids=affected_preflight_ids, affected_schedule_ids=affected_schedule_ids,
                evidence=evidence, checked_at=now,
            )

        if is_current:
            invalidation = self._preflight_invalidation_service.invalidate(task_id, reason=final_reason)
            invalidated = invalidation.is_invalid
            recorded_reason = invalidation.reason
        else:
            invalidated = True  # no longer the live preflight at all -- already non-actionable
            recorded_reason = already.reason if already is not None else final_reason

        return AgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationResult(
            task_id=task_id, snapshot_id=snapshot_id, preflight_id=snapshot.preflight_id,
            warranted=True, invalidated=invalidated, reason=recorded_reason,
            affected_preflight_ids=affected_preflight_ids, affected_schedule_ids=affected_schedule_ids,
            evidence=evidence, checked_at=now,
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustInvalidationError(
                f"{field_name} is required and must be a non-empty string"
            )
