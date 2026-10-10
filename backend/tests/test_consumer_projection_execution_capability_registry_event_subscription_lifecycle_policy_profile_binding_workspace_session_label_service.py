import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabel as Label,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelIndex as LabelIndex,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLabelService as LabelService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    label_service = LabelService(session_service)
    return pipeline_service, session_service, label_service


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


class TestWorkspaceSessionLabelService:
    def test_add_label(self):
        pipeline_service, session_service, label_service = _build()
        session = _start_session(pipeline_service, session_service)

        label = label_service.add(session.session_id, "environment", "staging")

        assert isinstance(label, Label)
        assert label.session_id == session.session_id
        assert label.key == "environment"
        assert label.value == "staging"

    def test_remove_label(self):
        pipeline_service, session_service, label_service = _build()
        session = _start_session(pipeline_service, session_service)

        label_service.add(session.session_id, "environment", "staging")
        label_service.remove(session.session_id, "environment")

        assert label_service.labels(session.session_id) == ()
        assert label_service.find("environment", "staging") == ()

        # removing an already-removed / never-set key is not an error
        label_service.remove(session.session_id, "environment")

    def test_session_labels(self):
        pipeline_service, session_service, label_service = _build()
        session = _start_session(pipeline_service, session_service)

        label_service.add(session.session_id, "environment", "staging")
        label_service.add(session.session_id, "team", "platform")

        labels = label_service.labels(session.session_id)

        assert {label.key for label in labels} == {"environment", "team"}

    def test_indexed_lookup(self):
        pipeline_service, session_service, label_service = _build()
        session_one = _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1")
        session_two = _start_session(pipeline_service, session_service, pipeline_id="pipeline-2", owner="user-2")

        label_service.add(session_one.session_id, "environment", "staging")
        label_service.add(session_two.session_id, "environment", "production")

        assert label_service.find("environment", "staging") == (session_one.session_id,)
        assert label_service.find("environment", "production") == (session_two.session_id,)
        assert label_service.find("environment", "unknown-value") == ()
        assert label_service.find("unknown-key", "staging") == ()

    def test_rebuild_index(self):
        pipeline_service, session_service, label_service = _build()
        session_one = _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1")
        session_two = _start_session(pipeline_service, session_service, pipeline_id="pipeline-2", owner="user-2")

        label_service.add(session_one.session_id, "environment", "staging")
        label_service.add(session_two.session_id, "environment", "staging")
        label_service.add(session_one.session_id, "team", "platform")

        rebuilt = label_service.rebuild_index()

        assert all(isinstance(entry, LabelIndex) for entry in rebuilt)

        by_key = {entry.label_key: entry.session_ids for entry in rebuilt}
        assert set(by_key["environment"]) == {session_one.session_id, session_two.session_id}
        assert by_key["team"] == (session_one.session_id,)

        # index still usable for exact-match lookups after a rebuild
        assert label_service.find("team", "platform") == (session_one.session_id,)

    def test_duplicate_label_rejection(self):
        pipeline_service, session_service, label_service = _build()
        session = _start_session(pipeline_service, session_service)

        label_service.add(session.session_id, "environment", "staging")

        with pytest.raises(Error):
            label_service.add(session.session_id, "environment", "production")

    def test_invalid_value_rejection(self):
        pipeline_service, session_service, label_service = _build()
        session = _start_session(pipeline_service, session_service)

        with pytest.raises(Error):
            label_service.add(session.session_id, "environment", "")

        with pytest.raises(Error):
            label_service.add(session.session_id, "environment", None)

    def test_blank_and_unknown_id_rejection(self):
        pipeline_service, session_service, label_service = _build()
        session = _start_session(pipeline_service, session_service)

        with pytest.raises(Error):
            label_service.add("   ", "environment", "staging")

        with pytest.raises(Error):
            label_service.add(session.session_id, "   ", "staging")

        with pytest.raises(Error):
            label_service.add("unknown-session", "environment", "staging")

        with pytest.raises(Error):
            label_service.remove("unknown-session", "environment")

        with pytest.raises(Error):
            label_service.labels("unknown-session")

        with pytest.raises(Error):
            label_service.find("   ", "staging")

        with pytest.raises(Error):
            label_service.find("environment", "   ")
