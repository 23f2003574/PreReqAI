import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason,
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshot,
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


class TestPackageBuilding:
    """A valid snapshot builds a package."""

    def test_package_builds_successfully(self):
        snapshot = _make_snapshot()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder()
        )
        package = builder.build(snapshot)

        assert package.projection_name == "workspace.bootstrap"
        assert package.capability == CAPABLE
        assert package.executable is True
        assert package.title == "Execution Capable"
        assert package.description == "Projection is capable of execution."


class TestProjectionPreserved:
    """projection_name is copied from the snapshot."""

    def test_projection_name_is_preserved(self):
        snapshot = _make_snapshot(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder()
        )
        package = builder.build(snapshot)

        assert package.projection_name == "workspace.attention"


class TestCapabilityPreserved:
    """capability is copied from the snapshot, not recomputed."""

    def test_capability_is_preserved(self):
        snapshot = _make_snapshot(
            capability=LIMITED,
            reason=APPROVAL_REQUIRED,
            executable=False,
            title="Limited Execution",
            description="Projection requires additional approval before execution.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder()
        )
        package = builder.build(snapshot)

        assert package.capability == LIMITED


class TestExecutablePreserved:
    """executable is copied from the snapshot, not recomputed."""

    def test_executable_flag_true_is_preserved(self):
        snapshot = _make_snapshot(capability=CAPABLE, executable=True)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder()
        )
        package = builder.build(snapshot)

        assert package.executable is True

    def test_executable_flag_false_is_preserved(self):
        snapshot = _make_snapshot(
            capability=INCAPABLE,
            reason=EXECUTION_BLOCKED,
            executable=False,
            title="Execution Incapable",
            description="Projection cannot be executed.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder()
        )
        package = builder.build(snapshot)

        assert package.executable is False


class TestTitlePreserved:
    """title is copied from the snapshot."""

    def test_title_is_preserved(self):
        snapshot = _make_snapshot(title="Execution Capable")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder()
        )
        package = builder.build(snapshot)

        assert package.title == "Execution Capable"


class TestDescriptionPreserved:
    """description is copied from the snapshot."""

    def test_description_is_preserved(self):
        snapshot = _make_snapshot(
            description="Projection is capable of execution."
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder()
        )
        package = builder.build(snapshot)

        assert package.description == "Projection is capable of execution."


class TestEmptyProjectionRejected:
    """A snapshot with an empty projection name is rejected."""

    def test_empty_projection_name_raises_error(self):
        snapshot = _make_snapshot(projection_name="")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageError
        ):
            builder.build(snapshot)


class TestDeterminism:
    """Building the same snapshot twice yields equal packages."""

    def test_equivalent_snapshot_produces_equivalent_packages(self):
        snapshot = _make_snapshot()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder()
        )

        first = builder.build(snapshot)
        second = builder.build(snapshot)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_snapshot(self):
        snapshot = _make_snapshot()
        snapshot_dict_before = snapshot.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder()
        )
        builder.build(snapshot)

        assert snapshot.to_dict() == snapshot_dict_before

    def test_package_carries_no_scheduler_or_executor_state(self):
        snapshot = _make_snapshot()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageBuilder()
        )
        package = builder.build(snapshot)

        assert set(package.to_dict().keys()) == {
            "projection_name",
            "capability",
            "executable",
            "title",
            "description",
        }
