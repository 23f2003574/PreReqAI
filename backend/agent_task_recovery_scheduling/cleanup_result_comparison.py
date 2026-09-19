from dataclasses import dataclass

from .cleanup_batch import BATCH_CLEANED, BATCH_FAILED
from .cleanup_result import LLMAgentTaskRecoveryPreflightScheduleCleanupResultService


class InvalidAgentTaskRecoveryScheduleCleanupResultComparisonError(ValueError):
    """Raised when compare() is given invalid arguments, or names a
    result that is not recorded for task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCleanupResultComparison:
    """compare()'s read-only diff of two persisted cleanup results.

    `count_changes` is always the four (name, previous, current) triples
    for processed, cleaned, skipped and failed; `appeared`/`disappeared`
    are schedule_ids only in the current/previous result;
    `outcome_changes` are (previous_entry, current_entry) pairs, the
    recorded batch entries verbatim, for a schedule in both whose
    outcome differs; `newly_failing`/`newly_cleaned` are schedule_ids
    that failed/were cleaned in the current result and did not in the
    previous one (including schedules new to it). `changed` is False
    exactly when nothing differs at all -- so two different results with
    the same content also compare unchanged."""

    task_id: str
    previous_result_id: str
    current_result_id: str
    changed: bool
    count_changes: tuple
    appeared: tuple
    disappeared: tuple
    outcome_changes: tuple
    newly_failing: tuple
    newly_cleaned: tuple


class LLMAgentTaskRecoveryPreflightScheduleCleanupResultComparisonService:
    """Shows what changed between two already-persisted cleanup results
    -- never reruns cleanup or writes: it reads both records from the #9
    result service and diffs their stored counts and per-schedule
    entries. Output follows the current result's entry order (previous
    order for what disappeared), so the same two results always give an
    equal comparison; comparing a result with itself is unchanged."""

    def __init__(self, result_service: LLMAgentTaskRecoveryPreflightScheduleCleanupResultService = None):
        self._result_service = (
            result_service if result_service is not None else LLMAgentTaskRecoveryPreflightScheduleCleanupResultService()
        )

    def compare(
        self, task_id: str, previous_result_id: str, current_result_id: str
    ) -> AgentTaskRecoveryScheduleCleanupResultComparison:
        """
        Raises:
            InvalidAgentTaskRecoveryScheduleCleanupResultComparisonError:
                If any argument is not a non-empty string, or either
                result_id names no recorded result for task_id
        """
        for value, name in (
            (task_id, "task_id"), (previous_result_id, "previous_result_id"), (current_result_id, "current_result_id"),
        ):
            if not value or not isinstance(value, str):
                raise InvalidAgentTaskRecoveryScheduleCleanupResultComparisonError(
                    f"{name} is required and must be a non-empty string"
                )

        previous = self._load(task_id, previous_result_id)
        current = self._load(task_id, current_result_id)
        before = {e.schedule_id: e for e in reversed(previous.entries)}
        after = {e.schedule_id: e for e in reversed(current.entries)}

        def outcome_of(entries, schedule_id):
            entry = entries.get(schedule_id)
            return entry.outcome if entry is not None else None

        current_ids = [e.schedule_id for e in current.entries]
        appeared = tuple(i for i in current_ids if i not in before)
        disappeared = tuple(e.schedule_id for e in previous.entries if e.schedule_id not in after)
        outcome_changes = tuple(
            (before[i], after[i]) for i in current_ids if i in before and before[i].outcome != after[i].outcome
        )
        newly_failing = tuple(
            i for i in current_ids if after[i].outcome == BATCH_FAILED and outcome_of(before, i) != BATCH_FAILED
        )
        newly_cleaned = tuple(
            i for i in current_ids if after[i].outcome == BATCH_CLEANED and outcome_of(before, i) != BATCH_CLEANED
        )
        count_changes = (
            ("processed", len(previous.entries), len(current.entries)),
            ("cleaned", previous.cleaned_count, current.cleaned_count),
            ("skipped", previous.skipped_count, current.skipped_count),
            ("failed", previous.failed_count, current.failed_count),
        )
        changed = (
            any(before_count != after_count for _, before_count, after_count in count_changes)
            or bool(appeared or disappeared or outcome_changes)
        )
        return AgentTaskRecoveryScheduleCleanupResultComparison(
            task_id=task_id, previous_result_id=previous_result_id, current_result_id=current_result_id,
            changed=changed, count_changes=count_changes, appeared=appeared, disappeared=disappeared,
            outcome_changes=outcome_changes, newly_failing=newly_failing, newly_cleaned=newly_cleaned,
        )

    def _load(self, task_id: str, result_id: str):
        record = self._result_service.get(task_id, result_id)
        if record is None:
            raise InvalidAgentTaskRecoveryScheduleCleanupResultComparisonError(
                f"no cleanup result {result_id!r} is recorded for task_id {task_id!r}"
            )
        return record
