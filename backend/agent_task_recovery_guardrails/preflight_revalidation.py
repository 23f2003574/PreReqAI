from .models import AgentTaskRecoveryPreflightRevalidationResult
from .preflight import LLMAgentTaskRecoveryPreflightService
from .preflight_invalidation import LLMAgentTaskRecoveryPreflightInvalidationService
from .preflight_store import LLMAgentTaskRecoveryPreflightStore

_NO_PRIOR_PREFLIGHT_REASON = "no stored preflight existed for this task"


class InvalidAgentTaskRecoveryPreflightRevalidationError(ValueError):
    """Raised when revalidate() is given invalid arguments, or a given
    preflight_id no longer matches the task's own current stored
    preflight."""


class LLMAgentTaskRecoveryPreflightRevalidationService:
    """Revalidates a previously stored Commit #4 preflight right before
    recovery execution, rebuilding a fresh executable decision when the
    old one can no longer be trusted -- never a second validation/policy
    framework (Rule): every step here is exactly one existing commit's
    own method, called unchanged:

        load the stored preflight        Commit #4 preflight_store.get()
        check freshness/invalidation     Commit #6 invalidate_if_stale()
                                          (itself reusing Commit #5)
        rebuild, only if genuinely stale Commit #3 preflight_service.run()
        persist the rebuilt preflight    Commit #4 preflight_store.save()

    No duplicated checks (Rule: "Reuse Commit #5 freshness and #6
    invalidation; no duplicated checks"): revalidate() calls Commit #6's
    own invalidate_if_stale() exactly once and never calls Commit #5's
    own check() directly itself -- invalidate_if_stale() already reuses
    it internally, so a second, independent freshness call here would be
    exactly the duplication the rule forbids.

    Never revives an invalid preflight (Rule): Commit #6's own
    invalidate_if_stale() itself now checks (see that commit's own fix)
    whether the existing preflight was ALREADY invalidated -- by a prior
    staleness finding, or by a wholly separate, explicit invalidate()
    call for a reason freshness alone could never detect -- before ever
    consulting freshness again; either case is treated identically here
    as "supersede it," never as "still valid because it happens to look
    fresh again."

    Read-only with respect to task/recovery state, never executes (Rule:
    "Never execute recovery"): the only write anywhere in this whole flow
    is Commit #4's own preflight_store.save() of a freshly-built preflight
    -- nothing here calls Commit #4(-of-agent_task_event_analytics)'s own
    execution service, or mutates backend.agent_task_lifecycle/
    agent_task_events directly.

    Preserves preflight history (Rule): a rebuild is always a NEW
    preflight_store.save() call, appended to Commit #4's own append-only
    history -- the superseded preflight is never rewritten or removed
    (Commit #4 has no update()/delete() at all).

    preflight_id, when given, is a caller's own assertion of which
    preflight it believes is current (Rule: "Use existing version/
    identity conventions" -- Commit #4's own preflight_id is this domain's
    one real identity for a stored preflight, so this is checked against
    it directly rather than inventing a separate version scheme): it must
    match the actual current stored preflight_id, or there is nothing
    meaningful to revalidate against a caller's now-outdated reference,
    and this raises rather than silently guessing which preflight was
    meant.

    Deterministic and safe to repeat (Rule): repeating revalidate() with
    nothing changed in between always finds the just-rebuilt preflight
    (built from, and therefore already consistent with, current state)
    reported fresh and not-already-invalid by Commit #6's own check, so
    the second call always reports was_revalidated=False with
    previous_preflight_id == current_preflight_id -- a stable fixed point,
    never an unbounded chain of rebuilds.
    """

    def __init__(
        self,
        preflight_store: LLMAgentTaskRecoveryPreflightStore = None,
        preflight_service: LLMAgentTaskRecoveryPreflightService = None,
        invalidation_service: LLMAgentTaskRecoveryPreflightInvalidationService = None,
    ):
        self._preflight_store = (
            preflight_store if preflight_store is not None else LLMAgentTaskRecoveryPreflightStore()
        )
        self._preflight_service = (
            preflight_service if preflight_service is not None else LLMAgentTaskRecoveryPreflightService()
        )
        self._invalidation_service = (
            invalidation_service
            if invalidation_service is not None
            else LLMAgentTaskRecoveryPreflightInvalidationService(preflight_store=self._preflight_store)
        )

    def revalidate(self, task_id: str, preflight_id: str = None) -> AgentTaskRecoveryPreflightRevalidationResult:
        """Revalidate task_id's current stored preflight (optionally
        asserting it is the one named by preflight_id), rebuilding a
        fresh one through Commit #3/#4 only if it is stale or already
        invalid.

        Raises:
            InvalidAgentTaskRecoveryPreflightRevalidationError: If
                task_id is not a non-empty string, or preflight_id is
                given and does not match the task's own current stored
                preflight (including when none is stored at all)
        """
        self._require_text(task_id)

        current = self._preflight_store.get(task_id)
        if preflight_id is not None:
            self._require_text(preflight_id, field_name="preflight_id")
            if current is None or current.preflight_id != preflight_id:
                raise InvalidAgentTaskRecoveryPreflightRevalidationError(
                    f"preflight_id {preflight_id!r} does not match task_id {task_id!r}'s own current "
                    "stored preflight (it may already have been superseded)"
                )

        if current is None:
            return self._rebuild(task_id, previous_preflight_id=None, stale_reasons=(_NO_PRIOR_PREFLIGHT_REASON,))

        invalidation = self._invalidation_service.invalidate_if_stale(task_id)
        if not invalidation.is_invalid:
            return AgentTaskRecoveryPreflightRevalidationResult(
                task_id=task_id,
                previous_preflight_id=current.preflight_id,
                current_preflight_id=current.preflight_id,
                was_revalidated=False,
                decision=current.decision,
                stale_reasons=(),
            )

        return self._rebuild(task_id, previous_preflight_id=current.preflight_id, stale_reasons=(invalidation.reason,))

    def _rebuild(
        self, task_id: str, previous_preflight_id, stale_reasons: tuple
    ) -> AgentTaskRecoveryPreflightRevalidationResult:
        fresh_result = self._preflight_service.run(task_id)
        new_record = self._preflight_store.save(fresh_result)

        return AgentTaskRecoveryPreflightRevalidationResult(
            task_id=task_id,
            previous_preflight_id=previous_preflight_id,
            current_preflight_id=new_record.preflight_id,
            was_revalidated=True,
            decision=new_record.decision,
            stale_reasons=stale_reasons,
        )

    @staticmethod
    def _require_text(value, field_name: str = "task_id") -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightRevalidationError(
                f"{field_name} is required and must be a non-empty string"
            )
