import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactAccessService,
    ExecutionArtifactConsumptionService,
    ExecutionArtifactConsumptionSnapshot,
    ExecutionArtifactConsumptionSnapshotError as Error,
    ExecutionArtifactConsumptionSnapshotService,
    ExecutionArtifactRetrievalService,
    ExecutionArtifactService,
    ExecutionArtifactVersionService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    version_service = ExecutionArtifactVersionService(artifact_service)
    access_service = ExecutionArtifactAccessService(artifact_service)
    retrieval_service = ExecutionArtifactRetrievalService(artifact_service, version_service, access_service)
    consumption_service = ExecutionArtifactConsumptionService(retrieval_service)
    snapshot_service = ExecutionArtifactConsumptionSnapshotService(consumption_service, version_service)
    return (
        pipeline_service,
        session_service,
        artifact_service,
        version_service,
        access_service,
        consumption_service,
        snapshot_service,
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


def _prepare_active_consumption(
    pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
):
    session = _start_session(pipeline_service, session_service)
    artifact = _register_artifact(artifact_service, session.session_id)
    version_service.create(artifact.artifact_id, "/tmp/output-v1.log")
    access_service.grant(artifact.artifact_id, "user-1", "READ")
    consumption = consumption_service.start("user-1", [artifact.artifact_id])
    return artifact, consumption


class TestExecutionArtifactConsumptionSnapshotService:
    def test_create_snapshot(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )

        snapshot = snapshot_service.create(consumption.consumption_id)

        assert isinstance(snapshot, ExecutionArtifactConsumptionSnapshot)
        assert snapshot.consumption_id == consumption.consumption_id
        assert snapshot.artifact_versions == {artifact.artifact_id: 1}

    def test_restore_snapshot(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        snapshot = snapshot_service.create(consumption.consumption_id)

        restored = snapshot_service.restore(snapshot.snapshot_id)

        assert set(restored.keys()) == {artifact.artifact_id}
        assert restored[artifact.artifact_id].version == 1
        assert restored[artifact.artifact_id].location == "/tmp/output-v1.log"

    def test_latest_lookup(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        snapshot_service.create(consumption.consumption_id)
        version_service.create(artifact.artifact_id, "/tmp/output-v2.log")
        second = snapshot_service.create(consumption.consumption_id)

        latest = snapshot_service.latest(consumption.consumption_id)

        assert latest == second
        assert latest.artifact_versions[artifact.artifact_id] == 2

    def test_history_ordering(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        first = snapshot_service.create(consumption.consumption_id)
        version_service.create(artifact.artifact_id, "/tmp/output-v2.log")
        second = snapshot_service.create(consumption.consumption_id)

        history = snapshot_service.history(consumption.consumption_id)

        assert [snapshot.snapshot_id for snapshot in history] == [first.snapshot_id, second.snapshot_id]

    def test_inactive_session_rejection(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service = (
            _build()
        )
        _artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        consumption_service.finish(consumption.consumption_id)

        with pytest.raises(Error):
            snapshot_service.create(consumption.consumption_id)

        with pytest.raises(Error):
            snapshot_service.create("unknown-consumption")

    def test_immutable_snapshot(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service = (
            _build()
        )
        artifact, consumption = _prepare_active_consumption(
            pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service
        )
        snapshot = snapshot_service.create(consumption.consumption_id)

        version_service.create(artifact.artifact_id, "/tmp/output-v2.log")
        second_artifact_id = "artifact-2"
        _register_artifact(artifact_service, artifact.session_id, second_artifact_id)
        version_service.create(second_artifact_id, "/tmp/artifact-2-v1.log")
        access_service.grant(second_artifact_id, "user-1", "READ")
        consumption_service.add(consumption.consumption_id, second_artifact_id)

        assert snapshot.artifact_versions == {artifact.artifact_id: 1}

        with pytest.raises(Exception):
            snapshot.artifact_versions = {}

        with pytest.raises(TypeError):
            snapshot.artifact_versions["tampered"] = 99

        refetched = snapshot_service.latest(consumption.consumption_id)
        assert refetched == snapshot
        assert "tampered" not in refetched.artifact_versions

    def test_rejects_unknown_snapshot(self):
        *_rest, snapshot_service = _build()

        with pytest.raises(Error):
            snapshot_service.restore("unknown-snapshot")

        with pytest.raises(Error):
            snapshot_service.latest("unknown-consumption")

        assert snapshot_service.history("unknown-consumption") == []
