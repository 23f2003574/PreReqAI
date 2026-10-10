from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedule as Schedule,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulerService as SchedulerService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    scheduler_service = SchedulerService(session_service)
    return pipeline_service, session_service, scheduler_service


def _create_pipeline(pipeline_service, pipeline_id):
    pipeline_service.create(
        Pipeline(
            pipeline_id=pipeline_id,
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )


def _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1"):
    _create_pipeline(pipeline_service, pipeline_id)
    return session_service.start(pipeline_id, owner=owner)


def _soon(seconds=5):
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def _schedule(schedule_id, session_id, trigger_at=None, recurrence=None, enabled=True):
    return Schedule(
        schedule_id=schedule_id,
        session_id=session_id,
        trigger_at=trigger_at if trigger_at is not None else _soon(),
        recurrence=recurrence,
        enabled=enabled,
    )


class TestWorkspaceSessionSchedulerService:
    def test_create_schedule(self):
        pipeline_service, session_service, scheduler_service = _build()
        session = _start_session(pipeline_service, session_service)

        trigger_at = _soon()
        created = scheduler_service.schedule(
            session.session_id, _schedule("schedule-1", session.session_id, trigger_at=trigger_at)
        )

        assert isinstance(created, Schedule)
        assert created.schedule_id == "schedule-1"
        assert created.session_id == session.session_id
        assert created.trigger_at == trigger_at

    def test_reschedule(self):
        pipeline_service, session_service, scheduler_service = _build()
        session = _start_session(pipeline_service, session_service)

        trigger_at = _soon()
        scheduler_service.schedule(
            session.session_id,
            _schedule("schedule-1", session.session_id, trigger_at=trigger_at, recurrence=timedelta(hours=1)),
        )

        result = scheduler_service.reschedule("schedule-1")

        assert isinstance(result, Result)
        assert result.schedule_id == "schedule-1"
        assert result.next_execution == trigger_at + timedelta(hours=1)

        with pytest.raises(Error):
            scheduler_service.reschedule("unknown-schedule")

    def test_cancel(self):
        pipeline_service, session_service, scheduler_service = _build()
        session = _start_session(pipeline_service, session_service)

        scheduler_service.schedule(session.session_id, _schedule("schedule-1", session.session_id))

        result = scheduler_service.cancel("schedule-1")

        assert isinstance(result, Result)
        assert result.schedule_id == "schedule-1"
        assert result.next_execution is None

        with pytest.raises(Error):
            scheduler_service.cancel("schedule-1")

    def test_next_execution_lookup(self):
        pipeline_service, session_service, scheduler_service = _build()
        session_one = _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1")
        session_two = _start_session(pipeline_service, session_service, pipeline_id="pipeline-2", owner="user-2")

        assert scheduler_service.next() is None

        scheduler_service.schedule(
            session_one.session_id, _schedule("schedule-1", session_one.session_id, trigger_at=_soon(20))
        )
        scheduler_service.schedule(
            session_two.session_id, _schedule("schedule-2", session_two.session_id, trigger_at=_soon(5))
        )

        soonest = scheduler_service.next()

        assert soonest.schedule_id == "schedule-2"

        pending = scheduler_service.pending()

        assert [schedule.schedule_id for schedule in pending] == ["schedule-2", "schedule-1"]

    def test_recurring_execution(self):
        pipeline_service, session_service, scheduler_service = _build()
        session = _start_session(pipeline_service, session_service)

        trigger_at = _soon()
        scheduler_service.schedule(
            session.session_id,
            _schedule("schedule-1", session.session_id, trigger_at=trigger_at, recurrence=timedelta(minutes=30)),
        )

        first = scheduler_service.reschedule("schedule-1")
        second = scheduler_service.reschedule("schedule-1")

        assert first.next_execution == trigger_at + timedelta(minutes=30)
        assert second.next_execution == trigger_at + timedelta(minutes=60)
        assert scheduler_service.next().trigger_at == second.next_execution

    def test_duplicate_schedule_rejection(self):
        pipeline_service, session_service, scheduler_service = _build()
        session = _start_session(pipeline_service, session_service)

        scheduler_service.schedule(session.session_id, _schedule("schedule-1", session.session_id))

        with pytest.raises(Error):
            scheduler_service.schedule(session.session_id, _schedule("schedule-2", session.session_id))

        scheduler_service.cancel("schedule-1")

        # freed immediately: the session can now be scheduled again
        recreated = scheduler_service.schedule(session.session_id, _schedule("schedule-3", session.session_id))
        assert recreated.schedule_id == "schedule-3"
