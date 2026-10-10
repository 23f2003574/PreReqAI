import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependency as Dependency,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionDependencyResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyService as DependencyService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    dependency_service = DependencyService(session_service)
    return pipeline_service, session_service, dependency_service


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


def _dependency(dependency_id, schedule_id, prerequisite_session_id):
    return Dependency(
        dependency_id=dependency_id,
        schedule_id=schedule_id,
        prerequisite_session_id=prerequisite_session_id,
    )


class TestWorkspaceSessionScheduleDependencyService:
    def test_add_dependency(self):
        pipeline_service, session_service, dependency_service = _build()
        prerequisite = _start_session(pipeline_service, session_service)

        added = dependency_service.add("schedule-1", _dependency("dep-1", "schedule-1", prerequisite.session_id))

        assert isinstance(added, Dependency)
        assert added.dependency_id == "dep-1"
        assert added.schedule_id == "schedule-1"
        assert added.prerequisite_session_id == prerequisite.session_id

        with pytest.raises(Error):
            dependency_service.add("schedule-2", _dependency("dep-2", "schedule-2", "unknown-session"))

        with pytest.raises(Error):
            dependency_service.add("schedule-1", _dependency("dep-1", "schedule-1", prerequisite.session_id))

    def test_remove_dependency(self):
        pipeline_service, session_service, dependency_service = _build()
        prerequisite = _start_session(pipeline_service, session_service)

        dependency_service.add("schedule-1", _dependency("dep-1", "schedule-1", prerequisite.session_id))
        dependency_service.remove("dep-1")

        result = dependency_service.validate("schedule-1")
        assert result.satisfied is True
        assert result.blocking_sessions == ()

        with pytest.raises(Error):
            dependency_service.remove("dep-1")

    def test_ready_schedule_detection(self):
        pipeline_service, session_service, dependency_service = _build()
        prerequisite = _start_session(pipeline_service, session_service)

        dependency_service.add("schedule-1", _dependency("dep-1", "schedule-1", prerequisite.session_id))

        assert dependency_service.ready() == ()

        session_service.finish(prerequisite.session_id, successful=True)

        assert dependency_service.ready() == ("schedule-1",)

    def test_blocked_schedule_detection(self):
        pipeline_service, session_service, dependency_service = _build()
        prerequisite = _start_session(pipeline_service, session_service)

        dependency_service.add("schedule-1", _dependency("dep-1", "schedule-1", prerequisite.session_id))

        assert dependency_service.blocked() == ("schedule-1",)

        session_service.finish(prerequisite.session_id, successful=True)

        assert dependency_service.blocked() == ()

    def test_cycle_rejection(self):
        pipeline_service, session_service, dependency_service = _build()
        session_x = _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1")
        session_y = _start_session(pipeline_service, session_service, pipeline_id="pipeline-2", owner="user-2")

        with pytest.raises(Error):
            dependency_service.add(
                session_x.session_id, _dependency("dep-self", session_x.session_id, session_x.session_id)
            )

        dependency_service.add(
            session_y.session_id, _dependency("dep-1", session_y.session_id, session_x.session_id)
        )

        with pytest.raises(Error):
            dependency_service.add(
                session_x.session_id, _dependency("dep-2", session_x.session_id, session_y.session_id)
            )

    def test_dependency_validation(self):
        pipeline_service, session_service, dependency_service = _build()
        prerequisite_one = _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1")
        prerequisite_two = _start_session(pipeline_service, session_service, pipeline_id="pipeline-2", owner="user-2")

        dependency_service.add("schedule-1", _dependency("dep-1", "schedule-1", prerequisite_one.session_id))
        dependency_service.add("schedule-1", _dependency("dep-2", "schedule-1", prerequisite_two.session_id))

        result = dependency_service.validate("schedule-1")
        assert isinstance(result, Result)
        assert result.satisfied is False
        assert result.blocking_sessions == (prerequisite_one.session_id, prerequisite_two.session_id)

        session_service.finish(prerequisite_one.session_id, successful=True)

        result = dependency_service.validate("schedule-1")
        assert result.satisfied is False
        assert result.blocking_sessions == (prerequisite_two.session_id,)

        session_service.finish(prerequisite_two.session_id, successful=True)

        result = dependency_service.validate("schedule-1")
        assert result.satisfied is True
        assert result.blocking_sessions == ()

        # a schedule with no dependencies is vacuously satisfied
        result = dependency_service.validate("schedule-without-dependencies")
        assert result.satisfied is True
        assert result.blocking_sessions == ()

        with pytest.raises(Error):
            dependency_service.validate("   ")
