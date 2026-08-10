from datetime import (
    timedelta,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactAccessService,
    ExecutionArtifactMount,
    ExecutionArtifactMountError as Error,
    ExecutionArtifactMountService,
    ExecutionArtifactRetrievalService,
    ExecutionArtifactService,
    ExecutionArtifactVersionService,
)


def _build(ttl=timedelta(minutes=15)):
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    version_service = ExecutionArtifactVersionService(artifact_service)
    access_service = ExecutionArtifactAccessService(artifact_service)
    retrieval_service = ExecutionArtifactRetrievalService(artifact_service, version_service, access_service)
    mount_service = ExecutionArtifactMountService(retrieval_service, ttl=ttl)
    return (
        pipeline_service,
        session_service,
        artifact_service,
        version_service,
        access_service,
        retrieval_service,
        mount_service,
    )


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


def _register_artifact(artifact_service, session_id, artifact_id="artifact-1"):
    return artifact_service.register(
        session_id,
        ExecutionArtifact(
            artifact_id=artifact_id,
            session_id=session_id,
            name="output.log",
            type="log",
            location="/tmp/output.log",
        ),
    )


def _prepare_retrievable_artifact(pipeline_service, session_service, artifact_service, version_service, access_service):
    session = _start_session(pipeline_service, session_service)
    artifact = _register_artifact(artifact_service, session.session_id)
    version_service.create(artifact.artifact_id, "/tmp/output-v1.log")
    access_service.grant(artifact.artifact_id, "user-1", "READ")
    return artifact


class TestExecutionArtifactMountService:
    def test_create_mount(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, _retrieval_service, mount_service = (
            _build()
        )
        artifact = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service
        )

        mount = mount_service.mount(artifact.artifact_id, "user-1")

        assert isinstance(mount, ExecutionArtifactMount)
        assert mount.artifact_id == artifact.artifact_id
        assert mount.consumer == "user-1"
        assert mount.path

    def test_mount_requires_retrieval_permission(self):
        pipeline_service, session_service, artifact_service, version_service, _access_service, _retrieval_service, mount_service = (
            _build()
        )
        session = _start_session(pipeline_service, session_service)
        artifact = _register_artifact(artifact_service, session.session_id)
        version_service.create(artifact.artifact_id, "/tmp/output-v1.log")

        with pytest.raises(Error):
            mount_service.mount(artifact.artifact_id, "user-1")

    def test_duplicate_mount_rejection(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, _retrieval_service, mount_service = (
            _build()
        )
        artifact = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service
        )

        mount_service.mount(artifact.artifact_id, "user-1")

        with pytest.raises(Error):
            mount_service.mount(artifact.artifact_id, "user-1")

    def test_unmount(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, _retrieval_service, mount_service = (
            _build()
        )
        artifact = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service
        )
        mount = mount_service.mount(artifact.artifact_id, "user-1")

        released = mount_service.unmount(mount.mount_id)

        assert released == mount
        assert mount_service.mounts("user-1") == []

        with pytest.raises(Error):
            mount_service.unmount(mount.mount_id)

    def test_unmount_allows_remount(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, _retrieval_service, mount_service = (
            _build()
        )
        artifact = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service
        )
        mount = mount_service.mount(artifact.artifact_id, "user-1")
        mount_service.unmount(mount.mount_id)

        remounted = mount_service.mount(artifact.artifact_id, "user-1")

        assert remounted.mount_id != mount.mount_id

    def test_expiry_detection(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, _retrieval_service, mount_service = (
            _build(ttl=timedelta(seconds=-1))
        )
        artifact = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service
        )

        mount = mount_service.mount(artifact.artifact_id, "user-1")

        assert mount_service.mounts("user-1") == []
        assert mount_service.expired() == [mount]

    def test_cleanup(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, _retrieval_service, mount_service = (
            _build(ttl=timedelta(seconds=-1))
        )
        artifact = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service
        )

        mount = mount_service.mount(artifact.artifact_id, "user-1")

        removed = mount_service.cleanup()

        assert removed == [mount]
        assert mount_service.expired() == []

        remounted = mount_service.mount(artifact.artifact_id, "user-1")
        assert remounted.mount_id != mount.mount_id

    def test_consumer_isolation(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, _retrieval_service, mount_service = (
            _build()
        )
        artifact = _prepare_retrievable_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service
        )
        access_service.grant(artifact.artifact_id, "user-2", "READ")

        first = mount_service.mount(artifact.artifact_id, "user-1")
        second = mount_service.mount(artifact.artifact_id, "user-2")

        assert mount_service.mounts("user-1") == [first]
        assert mount_service.mounts("user-2") == [second]

    def test_rejects_unknown_artifact(self):
        *_rest, mount_service = _build()

        with pytest.raises(Error):
            mount_service.mount("unknown-artifact", "user-1")
