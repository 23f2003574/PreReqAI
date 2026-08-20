import pytest

from backend.session import (
    ExecutionArtifactManifest,
    ExecutionArtifactManifestError as Error,
    ExecutionArtifactManifestService,
    ExecutionArtifactRegistryService,
    WorkspaceExecutionArtifactMetadataService,
    WorkspaceExecutionArtifactVersionService,
)


class _FakeStateRecord:
    def __init__(self, state):
        self.state = state


class _FakeRuntimeStateService:
    def __init__(self, known_runtimes=None):
        self._known_runtimes = set(known_runtimes or ())

    def state(self, runtime_id):
        if runtime_id not in self._known_runtimes:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return _FakeStateRecord("RUNNING")


def _build():
    runtime_state_service = _FakeRuntimeStateService({"runtime-1", "runtime-2"})
    registry = ExecutionArtifactRegistryService(runtime_state_service)
    versions = WorkspaceExecutionArtifactVersionService(registry)
    metadata = WorkspaceExecutionArtifactMetadataService(registry)
    manifests = ExecutionArtifactManifestService(registry, versions, metadata)
    return registry, versions, metadata, manifests


class TestExecutionArtifactManifestService:
    def test_generate_manifest(self):
        registry, versions, metadata, manifests = _build()
        artifact = registry.register("runtime-1", "model.bin", "MODEL", "/artifacts/model.bin")
        versions.create(artifact.artifact_id, "/artifacts/v1", "sha256:one")

        manifest = manifests.generate(artifact.artifact_id)

        assert isinstance(manifest, ExecutionArtifactManifest)
        assert manifest.artifact_id == artifact.artifact_id
        assert manifest.checksum

        fetched = manifests.get(manifest.manifest_id)

        assert fetched == manifest

    def test_version_and_metadata_inclusion(self):
        registry, versions, metadata, manifests = _build()
        artifact = registry.register("runtime-1", "dataset", "DATASET", "/artifacts/dataset")

        v1 = versions.create(artifact.artifact_id, "/artifacts/v1", "sha256:one")
        v2 = versions.create(artifact.artifact_id, "/artifacts/v2", "sha256:two")
        metadata.set(artifact.artifact_id, "owner", "alice")
        metadata.set(artifact.artifact_id, "rows", 100)

        manifest = manifests.generate(artifact.artifact_id)

        assert manifest.versions == (v1, v2)
        assert {entry.key for entry in manifest.metadata} == {"owner", "rows"}

    def test_deterministic_output(self):
        registry, versions, metadata, manifests = _build()
        artifact = registry.register("runtime-1", "report", "FILE", "/artifacts/report.txt")

        versions.create(artifact.artifact_id, "/artifacts/v1", "sha256:one")
        metadata.set(artifact.artifact_id, "b-key", "second")
        metadata.set(artifact.artifact_id, "a-key", "first")

        first = manifests.generate(artifact.artifact_id)
        second = manifests.generate(artifact.artifact_id)

        assert first.checksum == second.checksum
        assert [entry.key for entry in first.metadata] == ["a-key", "b-key"]

    def test_checksum_verification(self):
        registry, versions, metadata, manifests = _build()
        artifact = registry.register("runtime-1", "model", "MODEL", "/artifacts/model")
        versions.create(artifact.artifact_id, "/artifacts/v1", "sha256:one")

        manifest = manifests.generate(artifact.artifact_id)

        assert manifests.verify(manifest.manifest_id) is True

        versions.create(artifact.artifact_id, "/artifacts/v2", "sha256:two")

        assert manifests.verify(manifest.manifest_id) is False

    def test_immutable_manifest(self):
        registry, versions, metadata, manifests = _build()
        artifact = registry.register("runtime-1", "dataset", "DATASET", "/artifacts/dataset")
        versions.create(artifact.artifact_id, "/artifacts/v1", "sha256:one")

        first = manifests.generate(artifact.artifact_id)
        versions.create(artifact.artifact_id, "/artifacts/v2", "sha256:two")
        second = manifests.generate(artifact.artifact_id)

        assert first.versions == (versions.get(artifact.artifact_id, 1),)
        assert first != second
        assert manifests.history(artifact.artifact_id) == (first, second)

    def test_unknown_artifact_rejection(self):
        _, _, _, manifests = _build()

        with pytest.raises(Error):
            manifests.generate("unknown-artifact")

        with pytest.raises(Error):
            manifests.get("unknown-manifest")
