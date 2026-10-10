import pytest

from backend.session import (
    ExecutionArtifactRegistryService,
    WorkspaceExecutionArtifactVersion,
    WorkspaceExecutionArtifactVersionError as Error,
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
    service = WorkspaceExecutionArtifactVersionService(registry)
    return registry, service


class TestWorkspaceExecutionArtifactVersionService:
    def test_create_version(self):
        registry, service = _build()
        artifact = registry.register("runtime-1", "model.bin", "MODEL", "/artifacts/model.bin")

        version = service.create(artifact.artifact_id, "/artifacts/model-v1.bin", "sha256:abc")

        assert isinstance(version, WorkspaceExecutionArtifactVersion)
        assert version.artifact_id == artifact.artifact_id
        assert version.version == 1
        assert version.location == "/artifacts/model-v1.bin"
        assert version.checksum == "sha256:abc"

    def test_sequential_numbering(self):
        registry, service = _build()
        artifact = registry.register("runtime-1", "dataset", "DATASET", "/artifacts/dataset")

        first = service.create(artifact.artifact_id, "/artifacts/v1", "sha256:one")
        second = service.create(artifact.artifact_id, "/artifacts/v2", "sha256:two")
        third = service.create(artifact.artifact_id, "/artifacts/v3", "sha256:three")

        assert (first.version, second.version, third.version) == (1, 2, 3)

    def test_immutable_version(self):
        registry, service = _build()
        artifact = registry.register("runtime-1", "report", "FILE", "/artifacts/report.txt")

        first = service.create(artifact.artifact_id, "/artifacts/v1", "sha256:one")
        service.create(artifact.artifact_id, "/artifacts/v2", "sha256:two")

        refetched = service.get(artifact.artifact_id, 1)

        assert refetched == first
        assert refetched.location == "/artifacts/v1"
        assert refetched.checksum == "sha256:one"

    def test_latest_lookup(self):
        registry, service = _build()
        artifact = registry.register("runtime-1", "model", "MODEL", "/artifacts/model")

        service.create(artifact.artifact_id, "/artifacts/v1", "sha256:one")
        second = service.create(artifact.artifact_id, "/artifacts/v2", "sha256:two")

        assert service.latest(artifact.artifact_id) == second

    def test_history_ordering(self):
        registry, service = _build()
        artifact = registry.register("runtime-1", "dataset", "DATASET", "/artifacts/dataset")

        first = service.create(artifact.artifact_id, "/artifacts/v1", "sha256:one")
        second = service.create(artifact.artifact_id, "/artifacts/v2", "sha256:two")
        third = service.create(artifact.artifact_id, "/artifacts/v3", "sha256:three")

        history = service.history(artifact.artifact_id)

        assert history == (first, second, third)

    def test_checksum_validation(self):
        registry, service = _build()
        artifact = registry.register("runtime-1", "model", "MODEL", "/artifacts/model")

        with pytest.raises(Error):
            service.create(artifact.artifact_id, "/artifacts/v1", "")

        with pytest.raises(Error):
            service.create(artifact.artifact_id, "/artifacts/v1", None)
