import pytest

from backend.session import (
    ExecutionArtifactRegistryService,
    WorkspaceExecutionArtifact,
    WorkspaceExecutionArtifactError as Error,
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


def _build(known_runtimes=None):
    runtime_state_service = _FakeRuntimeStateService(
        known_runtimes or {"runtime-1", "runtime-2"}
    )
    return runtime_state_service, ExecutionArtifactRegistryService(runtime_state_service)


class TestExecutionArtifactRegistryService:
    def test_register_and_get(self):
        _, service = _build()

        artifact = service.register("runtime-1", "model.bin", "MODEL", "/artifacts/model.bin")

        assert isinstance(artifact, WorkspaceExecutionArtifact)
        assert artifact.runtime_id == "runtime-1"
        assert artifact.name == "model.bin"
        assert artifact.artifact_type == "MODEL"
        assert artifact.location == "/artifacts/model.bin"
        assert artifact.status == "ACTIVE"

        fetched = service.get(artifact.artifact_id)

        assert fetched == artifact

    def test_unknown_runtime_rejection(self):
        _, service = _build()

        with pytest.raises(Error):
            service.register("runtime-unknown", "file.txt", "FILE", "/artifacts/file.txt")

    def test_duplicate_name_rejection(self):
        _, service = _build()

        service.register("runtime-1", "report", "FILE", "/artifacts/report.txt")

        with pytest.raises(Error):
            service.register("runtime-1", "report", "FILE", "/artifacts/report-2.txt")

    def test_invalid_artifact_type(self):
        _, service = _build()

        with pytest.raises(Error):
            service.register("runtime-1", "report", "SPREADSHEET", "/artifacts/report.txt")

    def test_runtime_isolation(self):
        _, service = _build()

        service.register("runtime-1", "shared-name", "FILE", "/artifacts/one.txt")
        other = service.register("runtime-2", "shared-name", "FILE", "/artifacts/two.txt")

        assert other.runtime_id == "runtime-2"
        assert {artifact.artifact_id for artifact in service.list("runtime-1")} != {
            artifact.artifact_id for artifact in service.list("runtime-2")
        }

    def test_removal(self):
        _, service = _build()

        artifact = service.register("runtime-1", "dataset", "DATASET", "/artifacts/dataset")

        removed = service.remove(artifact.artifact_id)

        assert removed.status == "REMOVED"

        with pytest.raises(Error):
            service.get(artifact.artifact_id)

        with pytest.raises(Error):
            service.remove(artifact.artifact_id)

    def test_listing(self):
        _, service = _build()

        first = service.register("runtime-1", "first", "FILE", "/artifacts/first.txt")
        second = service.register("runtime-1", "second", "DIRECTORY", "/artifacts/second")
        service.register("runtime-2", "third", "MODEL", "/artifacts/third.bin")

        listed = service.list("runtime-1")

        assert {artifact.artifact_id for artifact in listed} == {
            first.artifact_id,
            second.artifact_id,
        }

        service.remove(first.artifact_id)

        assert {artifact.artifact_id for artifact in service.list("runtime-1")} == {
            second.artifact_id,
        }
