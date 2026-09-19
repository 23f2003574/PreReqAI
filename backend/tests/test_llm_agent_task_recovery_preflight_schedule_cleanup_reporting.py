from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.agent_task_recovery_scheduling import (
    EXPIRED_REASON,
    INVALIDATED_REASON,
    AgentTaskRecoveryScheduleCleanupResult,
    InvalidAgentTaskRecoveryScheduleCleanupReportingError,
    LLMAgentTaskRecoveryPreflightScheduleCleanupReportingService,
    LLMAgentTaskRecoveryPreflightScheduleCleanupService,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _result(cleaned=(), skipped=(), failures=(), task_id="task-1"):
    """cleaned: (schedule_id, reason) pairs."""
    return AgentTaskRecoveryScheduleCleanupResult(
        task_id=task_id, cleaned_count=len(cleaned), skipped_count=len(skipped),
        cleaned_schedule_ids=tuple(i for i, _ in cleaned), skipped_schedule_ids=tuple(skipped),
        cleaned_at=NOW, cleaned_reasons=tuple(cleaned), failures=tuple(failures),
    )


def _report(result, task_id="task-1"):
    return LLMAgentTaskRecoveryPreflightScheduleCleanupReportingService().report(task_id, result)


def test_empty_result_reports_all_zero():
    report = _report(_result())

    assert (report.cleaned_count, report.skipped_count, report.failure_count) == (0, 0, 0)
    assert report.cleaned_schedule_ids == report.skipped_schedule_ids == report.reason_counts == ()
    assert report.failures == ()
    assert report.cleaned_at == NOW


def test_successful_result_preserves_ids_and_counts_reasons():
    report = _report(_result(cleaned=[("s2", EXPIRED_REASON), ("s1", EXPIRED_REASON)]))

    assert report.cleaned_schedule_ids == ("s2", "s1")
    assert report.cleaned_count == 2
    assert report.reason_counts == ((EXPIRED_REASON, 2),)


def test_mixed_result_counts_by_reason_sorted_and_keeps_skipped():
    report = _report(
        _result(cleaned=[("s3", INVALIDATED_REASON), ("s1", EXPIRED_REASON)], skipped=["s2", "s4"])
    )

    assert report.reason_counts == ((EXPIRED_REASON, 1), (INVALIDATED_REASON, 1))
    assert report.skipped_schedule_ids == ("s2", "s4")
    assert report.skipped_count == 2


def test_failed_result_reports_failures_verbatim():
    report = _report(_result(cleaned=[("s1", EXPIRED_REASON)], failures=[("s2", "boom"), ("s3", "bang")]))

    assert report.failure_count == 2
    assert report.failures == (("s2", "boom"), ("s3", "bang"))
    assert report.cleaned_schedule_ids == ("s1",)


def test_report_is_deterministic_and_does_not_mutate_result():
    result = _result(cleaned=[("s1", EXPIRED_REASON)], skipped=["s2"], failures=[("s3", "boom")])
    before = replace(result)

    assert _report(result) == _report(result)
    assert result == before


def test_result_for_another_task_is_rejected():
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupReportingError):
        _report(_result(task_id="task-2"))


@pytest.mark.parametrize("task_id", [None, ""])
def test_invalid_task_id_is_rejected(task_id):
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupReportingError):
        _report(_result(), task_id=task_id)


def test_non_result_is_rejected():
    with pytest.raises(InvalidAgentTaskRecoveryScheduleCleanupReportingError):
        _report({"task_id": "task-1"})


class _RaisingExpiration:
    def check(self, task_id, schedule_id, now=None):
        raise RuntimeError("boom")


def test_cleanup_records_a_raising_schedule_as_failure_and_reports_it():
    class _Scheduling:
        def list(self, task_id):
            return [type("S", (), {"schedule_id": "s1", "status": "scheduled"})()]

    cleanup = LLMAgentTaskRecoveryPreflightScheduleCleanupService(
        scheduling_service=_Scheduling(), expiration_service=_RaisingExpiration(), reconciliation_service=object()
    )

    result = cleanup.cleanup("task-1", now=NOW)
    report = _report(result)

    assert (result.cleaned_count, result.skipped_count) == (0, 0)
    assert report.failures == (("s1", "boom"),)
