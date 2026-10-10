import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotError,
)


ACCEPT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT
REVIEW = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REVIEW


def _make_package(
    *,
    projection_name="workspace.bootstrap",
    decision=ACCEPT,
    executable=True,
    title="Capability Accepted",
    message="Projection satisfies all execution capability requirements.",
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage(
        projection_name=projection_name,
        decision=decision,
        executable=executable,
        title=title,
        message=message,
    )


class TestEmptyRegistry:
    """An empty registry produces an empty snapshot."""

    def test_empty_registry_snapshot(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotBuilder()

        snapshot = builder.build(registry)

        assert snapshot.packages == ()


class TestSinglePackage:
    """A registry with one package produces a one-package snapshot."""

    def test_single_package_snapshot(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        package = _make_package()
        registry.register(package)

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotBuilder()
        snapshot = builder.build(registry)

        assert snapshot.packages == (package,)


class TestMultiplePackagesSorted:
    """Multiple packages are included and sorted by projection_name."""

    def test_multiple_packages_are_sorted(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        bootstrap = _make_package(projection_name="workspace.bootstrap")
        actions = _make_package(projection_name="session.actions")
        attention = _make_package(projection_name="workspace.attention")

        registry.register(bootstrap)
        registry.register(actions)
        registry.register(attention)

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotBuilder()
        snapshot = builder.build(registry)

        assert snapshot.packages == (
            actions,
            attention,
            bootstrap,
        )


class TestImmutableTuple:
    """The snapshot's packages collection is an immutable tuple."""

    def test_packages_is_a_tuple(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package())

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotBuilder()
        snapshot = builder.build(registry)

        assert isinstance(snapshot.packages, tuple)

        with pytest.raises(AttributeError):
            snapshot.packages.append(_make_package())


class TestPackagesPreservedExactly:
    """Packages are copied exactly, with no recomputation."""

    def test_packages_are_preserved_exactly(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        package = _make_package(
            decision=REVIEW,
            executable=False,
            title="Capability Requires Review",
            message="Projection requires manual review before execution.",
        )
        registry.register(package)

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotBuilder()
        snapshot = builder.build(registry)

        assert snapshot.packages[0] is package


class TestInvalidRegistry:
    """A None or non-registry value is rejected."""

    def test_reject_none_registry(self):
        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotError
        ):
            builder.build(None)

    def test_reject_non_registry_object(self):
        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotError
        ):
            builder.build(object())


class TestDeterminism:
    """Building a snapshot twice from the same registry state agrees."""

    def test_equivalent_registry_state_produces_equivalent_snapshots(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package())

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotBuilder()

        first = builder.build(registry)
        second = builder.build(registry)

        assert first == second


class TestNoMutation:
    """Building a snapshot does not mutate the registry or its packages."""

    def test_builder_does_not_mutate_registry(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        package = _make_package()
        registry.register(package)
        package_dict = package.to_dict()

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotBuilder()
        builder.build(registry)

        assert registry.list_projection_names() == ("workspace.bootstrap",)
        assert package.to_dict() == package_dict

    def test_builder_has_no_external_dependencies(self):
        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotBuilder()

        assert builder.__dict__ == {}
