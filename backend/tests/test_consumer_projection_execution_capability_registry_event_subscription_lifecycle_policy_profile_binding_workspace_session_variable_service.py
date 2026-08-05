import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariable as Variable,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableService as VariableService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableSnapshot as Snapshot,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    variable_service = VariableService(session_service)
    return pipeline_service, session_service, variable_service


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


class TestWorkspaceSessionVariableService:
    def test_put_get_variable(self):
        pipeline_service, session_service, variable_service = _build()
        session = _start_session(pipeline_service, session_service)

        put = variable_service.put(session.session_id, "stage_count", 3)
        assert isinstance(put, Variable)
        assert put.value == 3

        got = variable_service.get(session.session_id, "stage_count")
        assert isinstance(got, Variable)
        assert got.value == 3

        assert variable_service.get(session.session_id, "missing") is None

    def test_overwrite_value(self):
        pipeline_service, session_service, variable_service = _build()
        session = _start_session(pipeline_service, session_service)

        variable_service.put(session.session_id, "status", "pending")
        first = variable_service.get(session.session_id, "status")

        variable_service.put(session.session_id, "status", "done")
        second = variable_service.get(session.session_id, "status")

        assert second.value == "done"
        assert second.updated_at >= first.updated_at

    def test_remove_variable(self):
        pipeline_service, session_service, variable_service = _build()
        session = _start_session(pipeline_service, session_service)

        variable_service.put(session.session_id, "status", "pending")
        variable_service.remove(session.session_id, "status")

        assert variable_service.get(session.session_id, "status") is None

        # removing an already-removed / never-set key is not an error
        variable_service.remove(session.session_id, "status")

    def test_snapshot_restore(self):
        pipeline_service, session_service, variable_service = _build()
        session = _start_session(pipeline_service, session_service)

        variable_service.put(session.session_id, "a", 1)
        variable_service.put(session.session_id, "b", 2)

        snapshot = variable_service.snapshot(session.session_id)
        assert isinstance(snapshot, Snapshot)
        assert dict(snapshot.variables) == {"a": 1, "b": 2}

        variable_service.put(session.session_id, "a", 99)
        variable_service.remove(session.session_id, "b")

        variable_service.restore(session.session_id, snapshot)

        assert variable_service.get(session.session_id, "a").value == 1
        assert variable_service.get(session.session_id, "b").value == 2

    def test_session_isolation(self):
        pipeline_service, session_service, variable_service = _build()
        session_one = _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1")
        session_two = _start_session(pipeline_service, session_service, pipeline_id="pipeline-2", owner="user-2")

        variable_service.put(session_one.session_id, "key", "session-one-value")
        variable_service.put(session_two.session_id, "key", "session-two-value")

        assert variable_service.get(session_one.session_id, "key").value == "session-one-value"
        assert variable_service.get(session_two.session_id, "key").value == "session-two-value"

    def test_invalid_restore_rejection(self):
        pipeline_service, session_service, variable_service = _build()
        session_one = _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1")
        session_two = _start_session(pipeline_service, session_service, pipeline_id="pipeline-2", owner="user-2")

        snapshot = variable_service.snapshot(session_one.session_id)

        with pytest.raises(Error):
            variable_service.restore(session_two.session_id, snapshot)

        with pytest.raises(Error):
            variable_service.restore(session_one.session_id, "not-a-snapshot")

        with pytest.raises(Error):
            variable_service.restore("   ", snapshot)

        with pytest.raises(Error):
            variable_service.restore("unknown-session", snapshot)

    def test_blank_and_unknown_id_rejection(self):
        pipeline_service, session_service, variable_service = _build()
        session = _start_session(pipeline_service, session_service)

        with pytest.raises(Error):
            variable_service.put("   ", "key", "value")

        with pytest.raises(Error):
            variable_service.put(session.session_id, "   ", "value")

        with pytest.raises(Error):
            variable_service.put("unknown-session", "key", "value")

        with pytest.raises(Error):
            variable_service.get("unknown-session", "key")

        with pytest.raises(Error):
            variable_service.remove("unknown-session", "key")

        with pytest.raises(Error):
            variable_service.snapshot("unknown-session")
