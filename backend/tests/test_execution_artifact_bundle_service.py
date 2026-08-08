import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ArtifactBundle,
    ArtifactBundleResult,
    ExecutionArtifact,
    ExecutionArtifactBundleError as Error,
    ExecutionArtifactBundleService,
    ExecutionArtifactIntegrityService,
    ExecutionArtifactService,
    ExecutionArtifactVersionService,
)


class _VersionRegistry:
    """
    Minimal stand-in for a version-ID resolver, satisfying the
    duck-typed `resolve(version_id)` contract the bundle service
    depends on, by indexing real ExecutionArtifactVersion objects as
    they are created.
    """

    def __init__(self):
        self._versions_by_id = {}

    def track(self, version):
        self._versions_by_id[version.version_id] = version
        return version

    def resolve(self, version_id):
        version = self._versions_by_id.get(version_id)

        if version is None:
            raise KeyError(version_id)

        return version


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    version_service = ExecutionArtifactVersionService(artifact_service)
    integrity_service = ExecutionArtifactIntegrityService()
    registry = _VersionRegistry()
    bundle_service = ExecutionArtifactBundleService(registry, integrity_service)
    return (
        pipeline_service,
        session_service,
        artifact_service,
        version_service,
        integrity_service,
        registry,
        bundle_service,
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


def _register_artifact(artifact_service, session_id, artifact_id):
    return artifact_service.register(
        session_id,
        ExecutionArtifact(
            artifact_id=artifact_id,
            session_id=session_id,
            name=f"{artifact_id}.log",
            type="log",
            location=f"/tmp/{artifact_id}.log",
        ),
    )


class TestExecutionArtifactBundleService:
    def test_create_bundle(self):
        (
            pipeline_service,
            session_service,
            artifact_service,
            version_service,
            integrity_service,
            registry,
            bundle_service,
        ) = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        version = registry.track(version_service.create("artifact-a", "/tmp/a-v1.log"))

        bundle = bundle_service.create(session.session_id, [version.version_id])

        assert isinstance(bundle, ArtifactBundle)
        assert bundle.session_id == session.session_id
        assert bundle.version_ids == (version.version_id,)

    def test_verify_bundle(self):
        (
            pipeline_service,
            session_service,
            artifact_service,
            version_service,
            integrity_service,
            registry,
            bundle_service,
        ) = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        version = registry.track(version_service.create("artifact-a", "/tmp/a-v1.log"))
        integrity_service.record(version.version_id, "abc123", algorithm="SHA256")

        bundle = bundle_service.create(session.session_id, [version.version_id])
        result = bundle_service.verify(bundle.bundle_id)

        assert isinstance(result, ArtifactBundleResult)
        assert result.bundle_id == bundle.bundle_id
        assert result.complete is True

    def test_incomplete_bundle(self):
        (
            pipeline_service,
            session_service,
            artifact_service,
            version_service,
            integrity_service,
            registry,
            bundle_service,
        ) = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        version = registry.track(version_service.create("artifact-a", "/tmp/a-v1.log"))

        bundle = bundle_service.create(session.session_id, [version.version_id])
        result = bundle_service.verify(bundle.bundle_id)

        assert result.complete is False

    def test_immutable_bundle(self):
        (
            pipeline_service,
            session_service,
            artifact_service,
            version_service,
            integrity_service,
            registry,
            bundle_service,
        ) = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        version = registry.track(version_service.create("artifact-a", "/tmp/a-v1.log"))

        bundle = bundle_service.create(session.session_id, [version.version_id])

        with pytest.raises(dataclasses.FrozenInstanceError):
            bundle.status = "TAMPERED"

        assert bundle_service.get(bundle.bundle_id).status == "CREATED"

    def test_session_listing(self):
        (
            pipeline_service,
            session_service,
            artifact_service,
            version_service,
            integrity_service,
            registry,
            bundle_service,
        ) = _build()
        session = _start_session(pipeline_service, session_service)
        _register_artifact(artifact_service, session.session_id, "artifact-a")
        version_1 = registry.track(version_service.create("artifact-a", "/tmp/a-v1.log"))
        version_2 = registry.track(version_service.create("artifact-a", "/tmp/a-v2.log"))

        first = bundle_service.create(session.session_id, [version_1.version_id])
        second = bundle_service.create(session.session_id, [version_2.version_id])

        assert bundle_service.list(session.session_id) == [first, second]

    def test_invalid_version_rejection(self):
        (
            pipeline_service,
            session_service,
            artifact_service,
            version_service,
            integrity_service,
            registry,
            bundle_service,
        ) = _build()
        session = _start_session(pipeline_service, session_service)

        with pytest.raises(Error):
            bundle_service.create(session.session_id, ["unknown-version"])

        with pytest.raises(Error):
            bundle_service.create(session.session_id, [])
