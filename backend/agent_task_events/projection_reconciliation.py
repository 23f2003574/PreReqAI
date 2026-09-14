from dataclasses import replace

from .models import PROJECTION_COMPARISON_FIELDS, AgentTaskProjectionDifference, AgentTaskProjectionReconciliationResult
from .projection import LLMAgentTaskEventProjectionService


class InvalidAgentTaskProjectionReconciliationError(ValueError):
    """Raised when check()/reconcile() is given invalid arguments."""


class LLMAgentTaskEventProjectionReconciliationService:
    """Detects and repairs a Commit #7 AgentTaskEventProjection that has
    fallen behind its own task's event stream -- never a second
    synchronization mechanism or event store (Rule: "Do not invent another
    synchronization or event-store abstraction"): every read and write
    here goes through Commit #7's own LLMAgentTaskEventProjectionService
    (get()/project()/refresh()), which itself already composes Commit #6's
    replay and Commit #3's timeline -- nothing is re-derived or re-queried
    a second, competing way.

    The event stream remains authoritative (Rule): "stale" here only ever
    means "this task's own persisted AgentTaskEventProjection disagrees
    with what project() would compute right now from that same event
    stream" -- never a comparison against backend.agent_task_lifecycle's
    own AgentTask (that authoritative cross-check is Commit #5's own
    STATE_MISMATCH job; Rule "Do not duplicate consistency validation from
    Commit #5" means this service never re-runs any of that module's six
    checks, and indeed never even imports backend.agent_task_lifecycle at
    all).

    check() is strictly read-only (Rule): it calls
    projection_service.get() and projection_service.project() -- neither
    of which ever writes -- and never calls refresh(). reconcile() calls
    check() first and, only when it found a real difference, calls
    projection_service.refresh() exactly once to persist the fresh
    projection; if check() already found the stored projection current,
    reconcile() performs no write at all (Rule: "reconcile() must be
    deterministic and idempotent" -- a second reconcile() call in a row,
    with no new events in between, always finds is_current already True
    and does nothing further).

    Comparison is field-by-field over PROJECTION_COMPARISON_FIELDS (see
    that constant's own docstring for why task_id/evaluated_at are
    excluded) -- a missing stored projection (get() returned None) is
    reported as its own single "projection" difference rather than seven
    spurious per-field differences against nothing (Rule: "Handle missing
    projections ... cleanly").
    """

    def __init__(self, projection_service: LLMAgentTaskEventProjectionService = None):
        self._projection_service = (
            projection_service if projection_service is not None else LLMAgentTaskEventProjectionService()
        )

    def check(self, task_id: str) -> AgentTaskProjectionReconciliationResult:
        """Compare task_id's stored projection against a freshly
        event-derived one. Never writes anything.

        Raises:
            InvalidAgentTaskProjectionReconciliationError: If task_id is
                not a non-empty string
        """
        self._require_text(task_id)

        stored = self._projection_service.get(task_id)
        expected = self._projection_service.project(task_id)
        differences = self._diff(stored, expected)

        return AgentTaskProjectionReconciliationResult(
            task_id=task_id,
            is_current=not differences,
            stored_projection=stored,
            expected_projection=expected,
            differences=tuple(differences),
            reconciled=False,
        )

    def reconcile(self, task_id: str) -> AgentTaskProjectionReconciliationResult:
        """check() task_id, and if it was not current, persist the fresh
        projection via Commit #7's own refresh(). The returned result
        still carries the differences check() found (Rule: "Do not
        silently discard projection differences") plus `reconciled=True`
        when a write actually happened; a task_id that was already
        current is returned unchanged, with `reconciled=False`.

        Raises:
            InvalidAgentTaskProjectionReconciliationError: If task_id is
                not a non-empty string
        """
        result = self.check(task_id)
        if result.is_current:
            return result

        self._projection_service.refresh(task_id)
        return replace(result, reconciled=True)

    @staticmethod
    def _diff(stored, expected) -> list:
        if stored is None:
            return [AgentTaskProjectionDifference(field="projection", stored=None, expected=expected)]

        differences = []
        for field_name in PROJECTION_COMPARISON_FIELDS:
            stored_value = getattr(stored, field_name)
            expected_value = getattr(expected, field_name)
            if stored_value != expected_value:
                differences.append(
                    AgentTaskProjectionDifference(field=field_name, stored=stored_value, expected=expected_value)
                )
        return differences

    @staticmethod
    def _require_text(task_id) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskProjectionReconciliationError(
                "task_id is required and must be a non-empty string"
            )
