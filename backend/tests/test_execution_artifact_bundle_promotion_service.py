import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ArtifactBundlePromotion,
    ExecutionArtifact,
    ExecutionArtifactBundlePromotionError as Error,
    ExecutionArtifactBundlePromotionService,
    ExecutionArtifactBundleService,
    ExecutionArtifactIntegrityService,
    ExecutionArtifactPromotionError,
    ExecutionArtifactPromotionService,
    ExecutionArtifactService,
    ExecutionArtifactVersionService,
)


class _VersionRegistry:
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
    promotion_service = ExecutionArtifactPromotionService(integrity_service)
    bundle_promotion_service = ExecutionArtifactBundlePromotionService(bundle_service, promotion_service, registry)
    return {
        "pipeline_service": pipeline_service,
        "session_service": session_service,
        "artifact_service": artifact_service,
        "version_service": version_service,
        "integrity_service": integrity_service,
        "registry": registry,
        "bundle_service": bundle_service,
        "promotion_service": promotion_service,
        "bundle_promotion_service": bundle_promotion_service,
    }


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


def _verified_bundle(env, artifact_ids, session_id):
    version_ids = []

    for artifact_id in artifact_ids:
        _register_artifact(env["artifact_service"], session_id, artifact_id)
        version = env["registry"].track(env["version_service"].create(artifact_id, f"/tmp/{artifact_id}-v1.log"))
        env["integrity_service"].record(version.version_id, "abc123", algorithm="SHA256")
        version_ids.append(version.version_id)

    return env["bundle_service"].create(session_id, version_ids)


class TestExecutionArtifactBundlePromotionService:
    def test_successful_promotion(self):
        env = _build()
        session = _start_session(env["pipeline_service"], env["session_service"])
        bundle = _verified_bundle(env, ["artifact-a"], session.session_id)

        promotion = env["bundle_promotion_service"].promote(bundle.bundle_id, "staging")

        assert isinstance(promotion, ArtifactBundlePromotion)
        assert promotion.status == "PROMOTED"
        assert promotion.source is None
        assert promotion.target == "staging"

    def test_incomplete_bundle_rejection(self):
        env = _build()
        session = _start_session(env["pipeline_service"], env["session_service"])
        _register_artifact(env["artifact_service"], session.session_id, "artifact-a")
        version = env["registry"].track(env["version_service"].create("artifact-a", "/tmp/artifact-a-v1.log"))
        bundle = env["bundle_service"].create(session.session_id, [version.version_id])

        with pytest.raises(Error):
            env["bundle_promotion_service"].promote(bundle.bundle_id, "staging")

    def test_atomic_failure(self):
        env = _build()
        session = _start_session(env["pipeline_service"], env["session_service"])
        bundle = _verified_bundle(env, ["artifact-a", "artifact-b"], session.session_id)

        first_version_id = bundle.version_ids[0]
        env["promotion_service"].promote(first_version_id, "production", artifact_id="artifact-a")

        with pytest.raises(Error):
            env["bundle_promotion_service"].promote(bundle.bundle_id, "production")

        with pytest.raises(ExecutionArtifactPromotionError):
            env["promotion_service"].current("artifact-b", "production")

    def test_rollback(self):
        env = _build()
        session = _start_session(env["pipeline_service"], env["session_service"])
        bundle = _verified_bundle(env, ["artifact-a"], session.session_id)

        promotion = env["bundle_promotion_service"].promote(bundle.bundle_id, "staging")
        rolled_back = env["bundle_promotion_service"].rollback(promotion.promotion_id)

        assert rolled_back.status == "ROLLED_BACK"

        with pytest.raises(Error):
            env["bundle_promotion_service"].current(bundle.bundle_id, "staging")

    def test_current_environment(self):
        env = _build()
        session = _start_session(env["pipeline_service"], env["session_service"])
        bundle = _verified_bundle(env, ["artifact-a"], session.session_id)

        promotion = env["bundle_promotion_service"].promote(bundle.bundle_id, "staging")

        assert env["bundle_promotion_service"].current(bundle.bundle_id, "staging") == promotion

    def test_promotion_history(self):
        env = _build()
        session = _start_session(env["pipeline_service"], env["session_service"])
        bundle = _verified_bundle(env, ["artifact-a"], session.session_id)

        first = env["bundle_promotion_service"].promote(bundle.bundle_id, "staging")
        second = env["bundle_promotion_service"].promote(bundle.bundle_id, "production")

        history = env["bundle_promotion_service"].history(bundle.bundle_id)

        assert [entry.promotion_id for entry in history] == [first.promotion_id, second.promotion_id]
        assert history[1].source == "staging"
