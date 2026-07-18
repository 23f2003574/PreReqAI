import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReport,
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySummary,
)


CAPABLE = ResearchWorkspaceConsumerProjectionExecutionCapability.CAPABLE
LIMITED = ResearchWorkspaceConsumerProjectionExecutionCapability.LIMITED
INCAPABLE = ResearchWorkspaceConsumerProjectionExecutionCapability.INCAPABLE

READY_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.READY
)
APPROVAL_REQUIRED = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.APPROVAL_REQUIRED
)
EXECUTION_BLOCKED = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.EXECUTION_BLOCKED
)


def _make_capability(
    *,
    projection_name="workspace.bootstrap",
    capability=CAPABLE,
    reason=READY_REASON,
    executable=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityReport(
        projection_name=projection_name,
        capability=capability,
        reason=reason,
        executable=executable,
    )


def _make_summary(
    *,
    projection_name="workspace.bootstrap",
    capability=CAPABLE,
    reason=READY_REASON,
    title="Execution Capable",
    description="Projection is capable of execution.",
    executable=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilitySummary(
        projection_name=projection_name,
        capability=capability,
        reason=reason,
        title=title,
        description=description,
        executable=executable,
    )


class TestSnapshotBuilding:
    """A valid, aligned pair builds a snapshot."""

    def test_snapshot_builds_successfully(self):
        capability = _make_capability()
        summary = _make_summary()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotBuilder()
        )
        snapshot = builder.build(capability, summary)

        assert snapshot.projection_name == "workspace.bootstrap"
        assert snapshot.capability == CAPABLE
        assert snapshot.reason == READY_REASON
        assert snapshot.executable is True
        assert snapshot.title == "Execution Capable"
        assert snapshot.description == "Projection is capable of execution."


class TestProjectionMismatch:
    """Artifacts describing different projections are rejected."""

    def test_projection_mismatch_raises_error(self):
        capability = _make_capability(projection_name="workspace.bootstrap")
        summary = _make_summary(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotError
        ):
            builder.build(capability, summary)


class TestCapabilityMismatch:
    """Artifacts disagreeing on the resolved capability are rejected."""

    def test_capability_mismatch_raises_error(self):
        capability = _make_capability(capability=CAPABLE)
        summary = _make_summary(
            capability=LIMITED,
            reason=APPROVAL_REQUIRED,
            title="Limited Execution",
            description="Projection requires additional approval before execution.",
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotError
        ):
            builder.build(capability, summary)


class TestReasonPreserved:
    """reason is copied from the capability report."""

    def test_reason_is_preserved(self):
        capability = _make_capability(
            capability=LIMITED,
            reason=APPROVAL_REQUIRED,
            executable=False,
        )
        summary = _make_summary(
            capability=LIMITED,
            reason=APPROVAL_REQUIRED,
            title="Limited Execution",
            description="Projection requires additional approval before execution.",
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotBuilder()
        )
        snapshot = builder.build(capability, summary)

        assert snapshot.reason == APPROVAL_REQUIRED


class TestExecutablePreserved:
    """executable is copied from the capability report."""

    def test_executable_is_preserved(self):
        capability = _make_capability(capability=INCAPABLE, executable=False)
        summary = _make_summary(
            capability=INCAPABLE,
            reason=EXECUTION_BLOCKED,
            title="Execution Incapable",
            description="Projection cannot be executed.",
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotBuilder()
        )
        snapshot = builder.build(capability, summary)

        assert snapshot.executable is False


class TestTitlePreserved:
    """title is copied from the capability summary."""

    def test_title_is_preserved(self):
        capability = _make_capability()
        summary = _make_summary(title="Execution Capable")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotBuilder()
        )
        snapshot = builder.build(capability, summary)

        assert snapshot.title == "Execution Capable"


class TestDescriptionPreserved:
    """description is copied from the capability summary."""

    def test_description_is_preserved(self):
        capability = _make_capability()
        summary = _make_summary(
            description="Projection is capable of execution."
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotBuilder()
        )
        snapshot = builder.build(capability, summary)

        assert snapshot.description == "Projection is capable of execution."


class TestDeterminism:
    """Building the same pair twice yields equal snapshots."""

    def test_equivalent_inputs_produce_equivalent_snapshots(self):
        capability = _make_capability()
        summary = _make_summary()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotBuilder()
        )

        first = builder.build(capability, summary)
        second = builder.build(capability, summary)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        capability = _make_capability()
        summary = _make_summary()

        capability_dict = capability.to_dict()
        summary_dict = summary.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotBuilder()
        )
        builder.build(capability, summary)

        assert capability.to_dict() == capability_dict
        assert summary.to_dict() == summary_dict

    def test_snapshot_carries_no_scheduler_or_persistence_state(self):
        capability = _make_capability()
        summary = _make_summary()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotBuilder()
        )
        snapshot = builder.build(capability, summary)

        assert set(snapshot.to_dict().keys()) == {
            "projection_name",
            "capability",
            "reason",
            "executable",
            "title",
            "description",
        }
