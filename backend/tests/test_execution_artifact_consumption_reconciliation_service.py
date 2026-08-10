import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ExecutionArtifact,
    ExecutionArtifactAccessService,
    ExecutionArtifactConsumptionDiff,
    ExecutionArtifactConsumptionReconciliationError as Error,
    ExecutionArtifactConsumptionReconciliationService,
    ExecutionArtifactConsumptionService,
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
    reconciliation_service = ExecutionArtifactConsumptionReconciliationService(
        consumption_service, snapshot_service, version_service
    )
    return (
        pipeline_service,
        session_service,
        artifact_service,
        version_service,
        access_service,
        consumption_service,
        snapshot_service,
        reconciliation_service,
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


def _prepare_artifact(
    pipeline_service, session_service, artifact_service, version_service, access_service, artifact_id, pipeline_id
):
    session = _start_session(pipeline_service, session_service, pipeline_id=pipeline_id)
    artifact = _register_artifact(artifact_service, session.session_id, artifact_id=artifact_id)
    version_service.create(artifact.artifact_id, f"/tmp/{artifact_id}-v1.log")
    access_service.grant(artifact.artifact_id, "user-1", "READ")
    return artifact


class TestExecutionArtifactConsumptionReconciliationService:
    def test_identical_state(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service, reconciliation_service = (
            _build()
        )
        artifact = _prepare_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-1", "pipeline-1"
        )
        consumption = consumption_service.start("user-1", [artifact.artifact_id])
        snapshot = snapshot_service.create(consumption.consumption_id)

        diff = reconciliation_service.compare(consumption.consumption_id, snapshot.snapshot_id)

        assert isinstance(diff, ExecutionArtifactConsumptionDiff)
        assert diff.added == ()
        assert diff.removed == ()
        assert dict(diff.changed) == {}

    def test_added_artifact(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service, reconciliation_service = (
            _build()
        )
        first = _prepare_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-1", "pipeline-1"
        )
        second = _prepare_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-2", "pipeline-2"
        )
        consumption = consumption_service.start("user-1", [first.artifact_id])
        snapshot = snapshot_service.create(consumption.consumption_id)
        consumption_service.add(consumption.consumption_id, second.artifact_id)

        diff = reconciliation_service.compare(consumption.consumption_id, snapshot.snapshot_id)

        assert diff.added == (second.artifact_id,)
        assert diff.removed == ()
        assert dict(diff.changed) == {}

    def test_removed_artifact(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service, reconciliation_service = (
            _build()
        )
        first = _prepare_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-1", "pipeline-1"
        )
        second = _prepare_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-2", "pipeline-2"
        )
        consumption = consumption_service.start("user-1", [first.artifact_id, second.artifact_id])
        snapshot = snapshot_service.create(consumption.consumption_id)
        consumption_service.remove(consumption.consumption_id, second.artifact_id)

        diff = reconciliation_service.compare(consumption.consumption_id, snapshot.snapshot_id)

        assert diff.added == ()
        assert diff.removed == (second.artifact_id,)
        assert dict(diff.changed) == {}

    def test_changed_version(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service, reconciliation_service = (
            _build()
        )
        artifact = _prepare_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-1", "pipeline-1"
        )
        consumption = consumption_service.start("user-1", [artifact.artifact_id])
        snapshot = snapshot_service.create(consumption.consumption_id)
        version_service.create(artifact.artifact_id, "/tmp/artifact-1-v2.log")

        diff = reconciliation_service.compare(consumption.consumption_id, snapshot.snapshot_id)

        assert diff.added == ()
        assert diff.removed == ()
        assert dict(diff.changed) == {artifact.artifact_id: (1, 2)}

        changes = reconciliation_service.changes(consumption.consumption_id)
        assert dict(changes.changed) == {artifact.artifact_id: (1, 2)}

    def test_compare_is_read_only(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service, reconciliation_service = (
            _build()
        )
        first = _prepare_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-1", "pipeline-1"
        )
        second = _prepare_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-2", "pipeline-2"
        )
        consumption = consumption_service.start("user-1", [first.artifact_id])
        snapshot = snapshot_service.create(consumption.consumption_id)
        consumption_service.add(consumption.consumption_id, second.artifact_id)

        before = consumption_service.get(consumption.consumption_id)
        reconciliation_service.compare(consumption.consumption_id, snapshot.snapshot_id)
        after = consumption_service.get(consumption.consumption_id)

        assert before == after
        assert snapshot_service.latest(consumption.consumption_id) == snapshot

    def test_apply_reconciliation(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service, reconciliation_service = (
            _build()
        )
        first = _prepare_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-1", "pipeline-1"
        )
        second = _prepare_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-2", "pipeline-2"
        )
        consumption = consumption_service.start("user-1", [first.artifact_id, second.artifact_id])
        snapshot = snapshot_service.create(consumption.consumption_id)
        consumption_service.remove(consumption.consumption_id, second.artifact_id)
        third = _prepare_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-3", "pipeline-3"
        )
        consumption_service.add(consumption.consumption_id, third.artifact_id)

        applied = reconciliation_service.apply(consumption.consumption_id, snapshot.snapshot_id)

        assert applied.added == (third.artifact_id,)
        assert applied.removed == (second.artifact_id,)

        reconciled = consumption_service.get(consumption.consumption_id)
        assert set(reconciled.artifact_ids) == {first.artifact_id, second.artifact_id}

        confirm_diff = reconciliation_service.compare(consumption.consumption_id, snapshot.snapshot_id)
        assert confirm_diff.added == ()
        assert confirm_diff.removed == ()

    def test_apply_requires_active_session(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service, reconciliation_service = (
            _build()
        )
        artifact = _prepare_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-1", "pipeline-1"
        )
        consumption = consumption_service.start("user-1", [artifact.artifact_id])
        snapshot = snapshot_service.create(consumption.consumption_id)
        consumption_service.finish(consumption.consumption_id)

        with pytest.raises(Error):
            reconciliation_service.apply(consumption.consumption_id, snapshot.snapshot_id)

    def test_rejects_unknown_consumption_or_snapshot(self):
        pipeline_service, session_service, artifact_service, version_service, access_service, consumption_service, snapshot_service, reconciliation_service = (
            _build()
        )
        artifact = _prepare_artifact(
            pipeline_service, session_service, artifact_service, version_service, access_service, "artifact-1", "pipeline-1"
        )
        consumption = consumption_service.start("user-1", [artifact.artifact_id])
        snapshot = snapshot_service.create(consumption.consumption_id)

        with pytest.raises(Error):
            reconciliation_service.compare("unknown-consumption", snapshot.snapshot_id)

        with pytest.raises(Error):
            reconciliation_service.compare(consumption.consumption_id, "unknown-snapshot")
