import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollection as Collection,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCollectionService as CollectionService,
)


def _build(auto_remove_completed=False):
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    collection_service = CollectionService(session_service, auto_remove_completed=auto_remove_completed)
    return pipeline_service, session_service, collection_service


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


class TestWorkspaceSessionCollectionService:
    def test_create_collection(self):
        _pipeline_service, _session_service, collection_service = _build()

        collection = collection_service.create("nightly-batch")

        assert isinstance(collection, Collection)
        assert collection.name == "nightly-batch"
        assert collection.session_ids == ()

    def test_add_remove_session(self):
        pipeline_service, session_service, collection_service = _build()
        session = _start_session(pipeline_service, session_service)
        collection = collection_service.create("nightly-batch")

        add_result = collection_service.add(collection.collection_id, session.session_id)
        assert isinstance(add_result, Result)
        assert add_result.member_count == 1

        remove_result = collection_service.remove(collection.collection_id, session.session_id)
        assert isinstance(remove_result, Result)
        assert remove_result.member_count == 0

        # removing a non-member is not an error
        collection_service.remove(collection.collection_id, session.session_id)

    def test_list_members(self):
        pipeline_service, session_service, collection_service = _build()
        session_one = _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1")
        session_two = _start_session(pipeline_service, session_service, pipeline_id="pipeline-2", owner="user-2")
        collection = collection_service.create("nightly-batch")

        collection_service.add(collection.collection_id, session_one.session_id)
        collection_service.add(collection.collection_id, session_two.session_id)

        members = collection_service.members(collection.collection_id)
        assert members == (session_one.session_id, session_two.session_id)

    def test_list_session_collections(self):
        pipeline_service, session_service, collection_service = _build()
        session = _start_session(pipeline_service, session_service)
        collection_one = collection_service.create("nightly-batch")
        collection_two = collection_service.create("release-candidates")

        collection_service.add(collection_one.collection_id, session.session_id)
        collection_service.add(collection_two.collection_id, session.session_id)

        memberships = collection_service.collections(session.session_id)
        assert memberships == (collection_one.collection_id, collection_two.collection_id)

    def test_duplicate_membership_rejection(self):
        pipeline_service, session_service, collection_service = _build()
        session = _start_session(pipeline_service, session_service)
        collection = collection_service.create("nightly-batch")

        collection_service.add(collection.collection_id, session.session_id)

        with pytest.raises(Error):
            collection_service.add(collection.collection_id, session.session_id)

    def test_delete_collection(self):
        pipeline_service, session_service, collection_service = _build()
        session = _start_session(pipeline_service, session_service)
        collection = collection_service.create("nightly-batch")

        collection_service.add(collection.collection_id, session.session_id)
        collection_service.delete(collection.collection_id)

        with pytest.raises(Error):
            collection_service.members(collection.collection_id)

        # the session's own membership record was cleaned up too
        assert collection_service.collections(session.session_id) == ()

        with pytest.raises(Error):
            collection_service.delete(collection.collection_id)

    def test_auto_remove_completed_sessions(self):
        pipeline_service, session_service, collection_service = _build(auto_remove_completed=True)
        session = _start_session(pipeline_service, session_service)
        collection = collection_service.create("nightly-batch")

        collection_service.add(collection.collection_id, session.session_id)
        assert collection_service.members(collection.collection_id) == (session.session_id,)

        session_service.finish(session.session_id, successful=True)

        assert collection_service.members(collection.collection_id) == ()
        assert collection_service.collections(session.session_id) == ()

    def test_blank_and_unknown_id_rejection(self):
        pipeline_service, session_service, collection_service = _build()
        session = _start_session(pipeline_service, session_service)
        collection = collection_service.create("nightly-batch")

        with pytest.raises(Error):
            collection_service.create("   ")

        with pytest.raises(Error):
            collection_service.add("   ", session.session_id)

        with pytest.raises(Error):
            collection_service.add(collection.collection_id, "   ")

        with pytest.raises(Error):
            collection_service.add("unknown-collection", session.session_id)

        with pytest.raises(Error):
            collection_service.add(collection.collection_id, "unknown-session")

        with pytest.raises(Error):
            collection_service.remove("unknown-collection", session.session_id)

        with pytest.raises(Error):
            collection_service.members("unknown-collection")

        with pytest.raises(Error):
            collection_service.collections("unknown-session")

        with pytest.raises(Error):
            collection_service.delete("unknown-collection")
