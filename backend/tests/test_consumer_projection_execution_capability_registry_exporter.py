import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExportError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter,
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
    """Exporting an empty registry produces an empty export."""

    def test_export_empty_registry(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        exporter = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter()

        export = exporter.export(registry)

        assert export.packages == ()
        assert export.total_projections == 0


class TestSinglePackage:
    """Exporting a registry with one package produces one entry."""

    def test_export_single_package(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        package = _make_package()
        registry.register(package)

        exporter = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter()
        export = exporter.export(registry)

        assert export.packages == (package,)
        assert export.total_projections == 1


class TestMultiplePackagesSorted:
    """Multiple packages are exported and sorted by projection_name."""

    def test_export_multiple_packages_sorted(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        bootstrap = _make_package(projection_name="workspace.bootstrap")
        actions = _make_package(projection_name="session.actions")
        attention = _make_package(projection_name="workspace.attention")

        registry.register(bootstrap)
        registry.register(actions)
        registry.register(attention)

        exporter = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter()
        export = exporter.export(registry)

        assert export.packages == (
            actions,
            attention,
            bootstrap,
        )
        assert export.total_projections == 3


class TestImmutablePackages:
    """The export's packages collection is an immutable tuple."""

    def test_packages_is_a_tuple(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package())

        exporter = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter()
        export = exporter.export(registry)

        assert isinstance(export.packages, tuple)

        with pytest.raises(AttributeError):
            export.packages.append(_make_package())


class TestRegistryUnchanged:
    """Exporting does not mutate the registry or its packages."""

    def test_registry_remains_unchanged(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        package = _make_package(
            decision=REVIEW,
            executable=False,
            title="Capability Requires Review",
            message="Projection requires manual review before execution.",
        )
        registry.register(package)
        package_dict = package.to_dict()

        exporter = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter()
        exporter.export(registry)

        assert registry.list_projection_names() == ("workspace.bootstrap",)
        assert package.to_dict() == package_dict


class TestInvalidRegistry:
    """A None or non-registry value is rejected."""

    def test_reject_none_registry(self):
        exporter = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExportError
        ):
            exporter.export(None)

    def test_reject_non_registry_object(self):
        exporter = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExportError
        ):
            exporter.export(object())


class TestDeterminism:
    """Exporting the same registry state twice produces equal exports."""

    def test_equivalent_registry_state_produces_equivalent_exports(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package())

        exporter = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter()

        first = exporter.export(registry)
        second = exporter.export(registry)

        assert first == second


class TestNoExecution:
    """The exporter has no external dependencies or state."""

    def test_exporter_has_no_external_dependencies(self):
        exporter = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter()

        assert exporter.__dict__ == {}
