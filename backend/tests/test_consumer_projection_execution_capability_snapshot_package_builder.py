import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptor,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason,
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshot,
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageError,
)


CAPABLE = ResearchWorkspaceConsumerProjectionExecutionCapability.CAPABLE
LIMITED = ResearchWorkspaceConsumerProjectionExecutionCapability.LIMITED
INCAPABLE = ResearchWorkspaceConsumerProjectionExecutionCapability.INCAPABLE

READY_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.READY
)
APPROVAL_REQUIRED_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.APPROVAL_REQUIRED
)
EXECUTION_BLOCKED_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.EXECUTION_BLOCKED
)

STANDARD = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.STANDARD
)
RESTRICTED = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.RESTRICTED
)
UNSUPPORTED = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.UNSUPPORTED
)


def _make_snapshot(
    *,
    projection_name="workspace.bootstrap",
    capability=CAPABLE,
    reason=READY_REASON,
    executable=True,
    title="Execution Capable",
    description="Projection is capable of execution.",
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshot(
        projection_name=projection_name,
        capability=capability,
        reason=reason,
        executable=executable,
        title=title,
        description=description,
    )


def _make_descriptor(
    *,
    projection_name="workspace.bootstrap",
    classification=STANDARD,
    title="Standard Capability",
    description="Projection supports normal execution.",
    executable=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityDescriptor(
        projection_name=projection_name,
        classification=classification,
        title=title,
        description=description,
        executable=executable,
    )


class TestPackageBuilding:
    """A valid, aligned pair builds a package."""

    def test_package_builds_successfully(self):
        snapshot = _make_snapshot()
        descriptor = _make_descriptor()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageBuilder()
        )
        package = builder.build(snapshot, descriptor)

        assert package.projection_name == "workspace.bootstrap"
        assert package.capability == CAPABLE
        assert package.classification == STANDARD
        assert package.executable is True
        assert package.title == "Standard Capability"
        assert package.description == "Projection supports normal execution."


class TestProjectionMismatch:
    """Artifacts describing different projections are rejected."""

    def test_projection_mismatch_raises_error(self):
        snapshot = _make_snapshot(projection_name="workspace.bootstrap")
        descriptor = _make_descriptor(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageError
        ):
            builder.build(snapshot, descriptor)


class TestExecutableMismatch:
    """Artifacts disagreeing on executability are rejected."""

    def test_executable_mismatch_raises_error(self):
        snapshot = _make_snapshot(capability=CAPABLE, executable=True)
        descriptor = _make_descriptor(
            classification=RESTRICTED,
            title="Restricted Capability",
            description="Projection requires additional approval before execution.",
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageError
        ):
            builder.build(snapshot, descriptor)


class TestCapabilityPreserved:
    """capability is copied from the capability snapshot."""

    def test_capability_is_preserved(self):
        snapshot = _make_snapshot(
            capability=INCAPABLE,
            reason=EXECUTION_BLOCKED_REASON,
            executable=False,
            title="Execution Incapable",
            description="Projection cannot be executed.",
        )
        descriptor = _make_descriptor(
            classification=UNSUPPORTED,
            title="Unsupported Capability",
            description="Projection is not capable of execution.",
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageBuilder()
        )
        package = builder.build(snapshot, descriptor)

        assert package.capability == INCAPABLE


class TestClassificationPreserved:
    """classification is copied from the capability descriptor."""

    def test_classification_is_preserved(self):
        snapshot = _make_snapshot(
            capability=LIMITED,
            reason=APPROVAL_REQUIRED_REASON,
            executable=False,
            title="Limited Execution",
            description="Projection requires additional approval before execution.",
        )
        descriptor = _make_descriptor(
            classification=RESTRICTED,
            title="Restricted Capability",
            description="Projection requires additional approval before execution.",
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageBuilder()
        )
        package = builder.build(snapshot, descriptor)

        assert package.classification == RESTRICTED


class TestTitlePreserved:
    """title is copied from the capability descriptor."""

    def test_title_is_preserved(self):
        snapshot = _make_snapshot()
        descriptor = _make_descriptor(title="Standard Capability")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageBuilder()
        )
        package = builder.build(snapshot, descriptor)

        assert package.title == "Standard Capability"


class TestDescriptionPreserved:
    """description is copied from the capability descriptor."""

    def test_description_is_preserved(self):
        snapshot = _make_snapshot()
        descriptor = _make_descriptor(
            description="Projection supports normal execution."
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageBuilder()
        )
        package = builder.build(snapshot, descriptor)

        assert package.description == "Projection supports normal execution."


class TestDeterminism:
    """Building the same pair twice yields equal packages."""

    def test_equivalent_inputs_produce_equivalent_packages(self):
        snapshot = _make_snapshot()
        descriptor = _make_descriptor()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageBuilder()
        )

        first = builder.build(snapshot, descriptor)
        second = builder.build(snapshot, descriptor)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        snapshot = _make_snapshot()
        descriptor = _make_descriptor()

        snapshot_dict = snapshot.to_dict()
        descriptor_dict = descriptor.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageBuilder()
        )
        builder.build(snapshot, descriptor)

        assert snapshot.to_dict() == snapshot_dict
        assert descriptor.to_dict() == descriptor_dict

    def test_package_carries_no_scheduler_or_approval_state(self):
        snapshot = _make_snapshot()
        descriptor = _make_descriptor()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageBuilder()
        )
        package = builder.build(snapshot, descriptor)

        assert set(package.to_dict().keys()) == {
            "projection_name",
            "capability",
            "classification",
            "executable",
            "title",
            "description",
        }
