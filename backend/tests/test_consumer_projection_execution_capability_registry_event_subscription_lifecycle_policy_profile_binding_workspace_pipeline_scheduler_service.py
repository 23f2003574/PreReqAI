import time

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueService as QueueService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedule as Schedule,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineScheduleResult as ScheduleResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerService as SchedulerService,
)


def _soon(seconds=0.05):
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def _schedule(schedule_id, pipeline_id=None, start_at=None, execution_window=5, depends_on=()):
    return Schedule(
        schedule_id=schedule_id,
        pipeline_id=pipeline_id if pipeline_id is not None else f"pipeline-for-{schedule_id}",
        start_at=start_at if start_at is not None else _soon(),
        execution_window=execution_window,
        depends_on=depends_on,
    )


class TestWorkspacePipelineSchedulerService:
    def test_create_schedule(self):
        service = SchedulerService()

        result = service.schedule(_schedule("schedule-1", pipeline_id="pipeline-1"))

        assert isinstance(result, ScheduleResult)
        assert result.scheduled is True
        assert [schedule.schedule_id for schedule in service.pending()] == ["schedule-1"]

        with pytest.raises(Error):
            service.schedule(_schedule("schedule-1"))  # duplicate schedule ID

        with pytest.raises(Error):
            service.schedule(_schedule("schedule-2", start_at=datetime.now(timezone.utc) - timedelta(seconds=1)))

        with pytest.raises(Error):
            service.schedule(None)

    def test_cancel_schedule(self):
        service = SchedulerService()
        service.schedule(_schedule("schedule-1"))

        service.cancel("schedule-1")

        assert service.pending() == ()

        # cancel is idempotent for an already-cancelled, but still known, schedule ID
        service.cancel("schedule-1")

        with pytest.raises(Error):
            service.cancel("unknown-schedule")

        with pytest.raises(Error):
            service.cancel("   ")

    def test_ready_pipeline_selection(self):
        service = SchedulerService()

        service.schedule(_schedule("early", start_at=_soon(0.05)))
        service.schedule(_schedule("later", start_at=_soon(0.15)))
        service.schedule(_schedule("far-future", start_at=_soon(30)))

        time.sleep(0.2)

        ready = service.ready()

        assert [schedule.schedule_id for schedule in ready] == ["early", "later"]

        # each ready schedule is delivered only once
        assert service.ready() == ()

        # far-future is not yet eligible
        assert [schedule.schedule_id for schedule in service.pending()] == ["far-future"]

    def test_dependency_enforcement(self):
        service = SchedulerService()

        service.schedule(_schedule("upstream", start_at=_soon(0.05)))
        service.schedule(_schedule("downstream", start_at=_soon(0.05), depends_on=("upstream",)))

        time.sleep(0.1)

        first_round = service.ready()
        assert [schedule.schedule_id for schedule in first_round] == ["upstream"]

        second_round = service.ready()
        assert [schedule.schedule_id for schedule in second_round] == ["downstream"]

    def test_circular_dependency_rejection(self):
        service = SchedulerService()

        service.schedule(_schedule("a", start_at=_soon(10), depends_on=("b",)))

        with pytest.raises(Error):
            service.schedule(_schedule("b", start_at=_soon(10), depends_on=("a",)))

        with pytest.raises(Error):
            service.schedule(_schedule("self-dependent", start_at=_soon(10), depends_on=("self-dependent",)))

    def test_reschedule(self):
        service = SchedulerService()
        service.schedule(_schedule("schedule-1", start_at=_soon(0.05)))

        time.sleep(0.1)

        dispatched = service.ready()
        assert [schedule.schedule_id for schedule in dispatched] == ["schedule-1"]
        assert service.ready() == ()

        result = service.reschedule("schedule-1")
        assert result.scheduled is True

        assert [schedule.schedule_id for schedule in service.pending()] == ["schedule-1"]
        assert [schedule.schedule_id for schedule in service.ready()] == ["schedule-1"]

        service.cancel("schedule-1")
        with pytest.raises(Error):
            service.reschedule("schedule-1")

        with pytest.raises(Error):
            service.reschedule("unknown-schedule")

    def test_skip_cancelled_schedules(self):
        service = SchedulerService()
        service.schedule(_schedule("keep", start_at=_soon(0.05)))
        service.schedule(_schedule("drop", start_at=_soon(0.05)))

        service.cancel("drop")

        time.sleep(0.1)

        ready = service.ready()
        assert [schedule.schedule_id for schedule in ready] == ["keep"]

    def test_integrates_with_execution_queue(self):
        scheduler_service = SchedulerService()
        queue_service = QueueService(concurrency_limit=10)

        scheduler_service.schedule(_schedule("schedule-1", pipeline_id="pipeline-1", start_at=_soon(0.05)))

        time.sleep(0.1)

        for ready_schedule in scheduler_service.ready():
            queue_service.enqueue(ready_schedule.pipeline_id, priority=1)

        item = queue_service.dequeue()
        assert item.pipeline_id == "pipeline-1"
