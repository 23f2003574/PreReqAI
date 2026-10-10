import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryService,
)


ACCEPT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT


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


class TestGet:
    """get() returns the registered package or None when absent."""

    def test_get_existing_projection(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        package = _make_package()
        registry.register(package)

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryService(
            registry
        )

        assert service.get("workspace.bootstrap") == package

    def test_get_missing_projection_returns_none(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryService(
            registry
        )

        assert service.get("workspace.attention") is None


class TestRequire:
    """require() returns the package or raises for a missing projection."""

    def test_require_existing_projection(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        package = _make_package()
        registry.register(package)

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryService(
            registry
        )

        assert service.require("workspace.bootstrap") == package

    def test_require_missing_projection_raises_error(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryService(
            registry
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryError
        ):
            service.require("workspace.attention")


class TestExists:
    """exists() is a boolean-only lookup."""

    def test_exists_true(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package())

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryService(
            registry
        )

        assert service.exists("workspace.bootstrap") is True

    def test_exists_false(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryService(
            registry
        )

        assert service.exists("workspace.bootstrap") is False


class TestListPackages:
    """list_packages() returns every package, sorted, as an immutable tuple."""

    def test_list_packages_sorted_and_immutable(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        bootstrap = _make_package(projection_name="workspace.bootstrap")
        actions = _make_package(projection_name="session.actions")
        attention = _make_package(projection_name="workspace.attention")

        registry.register(bootstrap)
        registry.register(actions)
        registry.register(attention)

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryService(
            registry
        )

        packages = service.list_packages()

        assert packages == (
            actions,
            attention,
            bootstrap,
        )
        assert isinstance(packages, tuple)


class TestRegistryUnchanged:
    """Query operations never mutate the underlying registry."""

    def test_registry_remains_unchanged(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        package = _make_package()
        registry.register(package)

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryService(
            registry
        )

        service.get("workspace.bootstrap")
        service.require("workspace.bootstrap")
        service.exists("workspace.bootstrap")
        service.list_packages()

        assert registry.list_projection_names() == ("workspace.bootstrap",)
        assert registry.get("workspace.bootstrap") == package


class TestDeterminism:
    """Repeated queries against the same registry state agree."""

    def test_repeated_queries_are_deterministic(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package())

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryQueryService(
            registry
        )

        assert service.get("workspace.bootstrap") == service.get(
            "workspace.bootstrap"
        )
        assert service.list_packages() == service.list_packages()
