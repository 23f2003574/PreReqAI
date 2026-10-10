import pytest

from backend.session import (
    ExecutionArtifactRegistryService,
    WorkspaceExecutionArtifactMetadata,
    WorkspaceExecutionArtifactMetadataError as Error,
    WorkspaceExecutionArtifactMetadataService,
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
    service = WorkspaceExecutionArtifactMetadataService(registry)
    return registry, service


class TestWorkspaceExecutionArtifactMetadataService:
    def test_set_and_get(self):
        registry, service = _build()
        artifact = registry.register("runtime-1", "model.bin", "MODEL", "/artifacts/model.bin")

        entry = service.set(artifact.artifact_id, "framework", "pytorch")

        assert isinstance(entry, WorkspaceExecutionArtifactMetadata)
        assert entry.artifact_id == artifact.artifact_id
        assert entry.key == "framework"
        assert entry.value == "pytorch"

        fetched = service.get(artifact.artifact_id, "framework")

        assert fetched == entry

    def test_update_existing_key(self):
        registry, service = _build()
        artifact = registry.register("runtime-1", "dataset", "DATASET", "/artifacts/dataset")

        service.set(artifact.artifact_id, "rows", 100)
        updated = service.set(artifact.artifact_id, "rows", 200)

        assert updated.value == 200
        assert service.get(artifact.artifact_id, "rows").value == 200
        assert len(service.all(artifact.artifact_id)) == 1

    def test_remove(self):
        registry, service = _build()
        artifact = registry.register("runtime-1", "report", "FILE", "/artifacts/report.txt")

        service.set(artifact.artifact_id, "author", "alice")
        removed = service.remove(artifact.artifact_id, "author")

        assert removed.value == "alice"

        with pytest.raises(Error):
            service.get(artifact.artifact_id, "author")

    def test_artifact_isolation(self):
        registry, service = _build()
        first = registry.register("runtime-1", "first", "FILE", "/artifacts/first.txt")
        second = registry.register("runtime-1", "second", "FILE", "/artifacts/second.txt")

        service.set(first.artifact_id, "owner", "alice")
        service.set(second.artifact_id, "owner", "bob")

        assert service.get(first.artifact_id, "owner").value == "alice"
        assert service.get(second.artifact_id, "owner").value == "bob"
        assert len(service.all(first.artifact_id)) == 1
        assert len(service.all(second.artifact_id)) == 1

    def test_metadata_search(self):
        registry, service = _build()
        first = registry.register("runtime-1", "first", "MODEL", "/artifacts/first.bin")
        second = registry.register("runtime-2", "second", "MODEL", "/artifacts/second.bin")

        service.set(first.artifact_id, "stage", "production")
        service.set(second.artifact_id, "stage", "staging")

        results = service.search("stage", "production")

        assert {entry.artifact_id for entry in results} == {first.artifact_id}

    def test_removed_artifact_rejection(self):
        registry, service = _build()
        artifact = registry.register("runtime-1", "temp", "FILE", "/artifacts/temp.txt")
        registry.remove(artifact.artifact_id)

        with pytest.raises(Error):
            service.set(artifact.artifact_id, "key", "value")

        with pytest.raises(Error):
            service.get(artifact.artifact_id, "key")

        with pytest.raises(Error):
            service.all(artifact.artifact_id)
