import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ArtifactBundleManifest,
    ExecutionArtifact,
    ExecutionArtifactBundleManifestError as Error,
    ExecutionArtifactBundleManifestService,
    ExecutionArtifactBundleService,
    ExecutionArtifactIntegrityService,
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
    manifest_service = ExecutionArtifactBundleManifestService(bundle_service, integrity_service, registry)

    pipeline_service.create(
        Pipeline(
            pipeline_id="pipeline-1",
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )
    session = session_service.start("pipeline-1", owner="user-1")

    return {
        "artifact_service": artifact_service,
        "version_service": version_service,
        "integrity_service": integrity_service,
        "registry": registry,
        "bundle_service": bundle_service,
        "manifest_service": manifest_service,
        "session": session,
    }


def _register_artifact(env, artifact_id):
    env["artifact_service"].register(
        env["session"].session_id,
        ExecutionArtifact(
            artifact_id=artifact_id,
            session_id=env["session"].session_id,
            name=f"{artifact_id}.log",
            type="log",
            location=f"/tmp/{artifact_id}.log",
        ),
    )


def _verified_bundle(env, artifact_ids):
    version_ids = []

    for artifact_id in artifact_ids:
        _register_artifact(env, artifact_id)
        version = env["registry"].track(env["version_service"].create(artifact_id, f"/tmp/{artifact_id}-v1.log"))
        env["integrity_service"].record(version.version_id, f"checksum-{artifact_id}", algorithm="SHA256")
        version_ids.append(version.version_id)

    return env["bundle_service"].create(env["session"].session_id, version_ids)


class TestExecutionArtifactBundleManifestService:
    def test_generate_manifest(self):
        env = _build()
        bundle = _verified_bundle(env, ["artifact-a", "artifact-b"])

        manifest = env["manifest_service"].generate(bundle.bundle_id)

        assert isinstance(manifest, ArtifactBundleManifest)
        assert [entry.version_id for entry in manifest.entries] == list(bundle.version_ids)
        assert [entry.artifact_id for entry in manifest.entries] == ["artifact-a", "artifact-b"]
        assert manifest.entries[0].checksum == "checksum-artifact-a"

    def test_deterministic_fingerprint(self):
        env = _build()
        bundle = _verified_bundle(env, ["artifact-a", "artifact-b"])

        first = env["manifest_service"].generate(bundle.bundle_id)
        second = env["manifest_service"].generate(bundle.bundle_id)

        assert first.fingerprint == second.fingerprint
        assert first.fingerprint != ""

    def test_verify_manifest(self):
        env = _build()
        bundle = _verified_bundle(env, ["artifact-a"])
        env["manifest_service"].generate(bundle.bundle_id)

        assert env["manifest_service"].verify(bundle.bundle_id) is True

    def test_manifest_diff(self):
        env = _build()
        bundle = _verified_bundle(env, ["artifact-a"])
        current = env["manifest_service"].generate(bundle.bundle_id)

        tampered_entry = dataclasses.replace(current.entries[0], checksum="tampered-checksum")
        expected = dataclasses.replace(current, entries=(tampered_entry,))

        diff = env["manifest_service"].diff(bundle.bundle_id, expected)

        assert diff["added"] == []
        assert diff["removed"] == []
        assert [entry.version_id for entry in diff["changed"]] == [current.entries[0].version_id]

    def test_missing_checksum_rejection(self):
        env = _build()
        _register_artifact(env, "artifact-a")
        version = env["registry"].track(env["version_service"].create("artifact-a", "/tmp/artifact-a-v1.log"))
        bundle = env["bundle_service"].create(env["session"].session_id, [version.version_id])

        with pytest.raises(Error):
            env["manifest_service"].generate(bundle.bundle_id)
