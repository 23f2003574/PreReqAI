import pytest

from backend.session import (
    ExecutionArtifactRegistryService,
    WorkspaceExecutionArtifactLineage,
    WorkspaceExecutionArtifactLineageError as Error,
    WorkspaceExecutionArtifactLineageService,
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
    lineage = WorkspaceExecutionArtifactLineageService(registry, versions)
    return registry, versions, lineage


class TestWorkspaceExecutionArtifactLineageService:
    def test_record_lineage(self):
        registry, versions, lineage = _build()
        parent_artifact = registry.register("runtime-1", "raw", "DATASET", "/artifacts/raw")
        parent_version = versions.create(parent_artifact.artifact_id, "/artifacts/raw-v1", "sha256:raw")

        child_artifact = registry.register("runtime-1", "cleaned", "DATASET", "/artifacts/cleaned")
        child_version = versions.create(child_artifact.artifact_id, "/artifacts/cleaned-v1", "sha256:cleaned")

        record = lineage.record(
            child_artifact.artifact_id,
            child_version.version_id,
            "runtime-1",
            parent_artifact_id=parent_artifact.artifact_id,
            parent_version_id=parent_version.version_id,
        )

        assert isinstance(record, WorkspaceExecutionArtifactLineage)
        assert record.artifact_id == child_artifact.artifact_id
        assert record.version_id == child_version.version_id
        assert record.parent_artifact_id == parent_artifact.artifact_id
        assert record.parent_version_id == parent_version.version_id

    def test_parent_child_lookup(self):
        registry, versions, lineage = _build()
        parent_artifact = registry.register("runtime-1", "raw", "DATASET", "/artifacts/raw")
        parent_version = versions.create(parent_artifact.artifact_id, "/artifacts/raw-v1", "sha256:raw")

        child_artifact = registry.register("runtime-1", "cleaned", "DATASET", "/artifacts/cleaned")
        child_version = versions.create(child_artifact.artifact_id, "/artifacts/cleaned-v1", "sha256:cleaned")

        record = lineage.record(
            child_artifact.artifact_id,
            child_version.version_id,
            "runtime-1",
            parent_artifact_id=parent_artifact.artifact_id,
            parent_version_id=parent_version.version_id,
        )

        assert lineage.parents(child_artifact.artifact_id) == (record,)
        assert lineage.children(parent_artifact.artifact_id) == (record,)
        assert lineage.parents(parent_artifact.artifact_id) == ()
        assert lineage.children(child_artifact.artifact_id) == ()

    def test_root_resolution(self):
        registry, versions, lineage = _build()
        root_artifact = registry.register("runtime-1", "root", "DATASET", "/artifacts/root")
        root_version = versions.create(root_artifact.artifact_id, "/artifacts/root-v1", "sha256:root")
        lineage.record(root_artifact.artifact_id, root_version.version_id, "runtime-1")

        mid_artifact = registry.register("runtime-1", "mid", "DATASET", "/artifacts/mid")
        mid_version = versions.create(mid_artifact.artifact_id, "/artifacts/mid-v1", "sha256:mid")
        lineage.record(
            mid_artifact.artifact_id,
            mid_version.version_id,
            "runtime-1",
            parent_artifact_id=root_artifact.artifact_id,
            parent_version_id=root_version.version_id,
        )

        leaf_artifact = registry.register("runtime-1", "leaf", "DATASET", "/artifacts/leaf")
        leaf_version = versions.create(leaf_artifact.artifact_id, "/artifacts/leaf-v1", "sha256:leaf")
        lineage.record(
            leaf_artifact.artifact_id,
            leaf_version.version_id,
            "runtime-1",
            parent_artifact_id=mid_artifact.artifact_id,
            parent_version_id=mid_version.version_id,
        )

        assert lineage.root(leaf_version.version_id) == root_version.version_id
        trace = lineage.trace(leaf_version.version_id)
        assert [record.version_id for record in trace] == [
            leaf_version.version_id,
            mid_version.version_id,
            root_version.version_id,
        ]

    def test_cycle_detection(self):
        registry, versions, lineage = _build()
        artifact_a = registry.register("runtime-1", "a", "DATASET", "/artifacts/a")
        version_a = versions.create(artifact_a.artifact_id, "/artifacts/a-v1", "sha256:a")

        artifact_b = registry.register("runtime-1", "b", "DATASET", "/artifacts/b")
        version_b = versions.create(artifact_b.artifact_id, "/artifacts/b-v1", "sha256:b")

        lineage.record(
            artifact_a.artifact_id,
            version_a.version_id,
            "runtime-1",
            parent_artifact_id=artifact_b.artifact_id,
            parent_version_id=version_b.version_id,
        )
        lineage.record(
            artifact_b.artifact_id,
            version_b.version_id,
            "runtime-1",
            parent_artifact_id=artifact_a.artifact_id,
            parent_version_id=version_a.version_id,
        )

        with pytest.raises(Error):
            lineage.trace(version_a.version_id)

        with pytest.raises(Error):
            lineage.root(version_b.version_id)

    def test_self_lineage_rejection(self):
        registry, versions, lineage = _build()
        artifact = registry.register("runtime-1", "solo", "DATASET", "/artifacts/solo")
        version = versions.create(artifact.artifact_id, "/artifacts/solo-v1", "sha256:solo")

        with pytest.raises(Error):
            lineage.record(
                artifact.artifact_id,
                version.version_id,
                "runtime-1",
                parent_artifact_id=artifact.artifact_id,
                parent_version_id=version.version_id,
            )

    def test_missing_parent_rejection(self):
        registry, versions, lineage = _build()
        artifact = registry.register("runtime-1", "child", "DATASET", "/artifacts/child")
        version = versions.create(artifact.artifact_id, "/artifacts/child-v1", "sha256:child")

        with pytest.raises(Error):
            lineage.record(
                artifact.artifact_id,
                version.version_id,
                "runtime-1",
                parent_artifact_id="unknown-artifact",
                parent_version_id="unknown-version",
            )

        other_artifact = registry.register("runtime-1", "other", "DATASET", "/artifacts/other")

        with pytest.raises(Error):
            lineage.record(
                artifact.artifact_id,
                version.version_id,
                "runtime-1",
                parent_artifact_id=other_artifact.artifact_id,
                parent_version_id="unknown-version",
            )
