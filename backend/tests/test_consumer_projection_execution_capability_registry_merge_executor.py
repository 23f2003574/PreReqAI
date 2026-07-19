import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutionError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan,
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


def _registry(*packages):
    registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()

    for package in packages:
        registry.register(package)

    return registry


def _plan(*, additions=(), updates=(), unchanged=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergePlan(
        additions=tuple(additions),
        updates=tuple(updates),
        unchanged=tuple(unchanged),
    )


def _export(registry):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter().export(
        registry
    )


class TestEmptyMerge:
    """An empty plan against an empty registry produces an empty registry."""

    def test_empty_merge(self):
        registry = _registry()
        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor()

        merged = executor.execute(registry, _plan())

        assert merged.list_projection_names() == ()


class TestAddProjection:
    """An addition is present in the merged registry."""

    def test_add_projection(self):
        registry = _registry()
        addition = _make_package(projection_name="workspace.export")

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor()
        merged = executor.execute(registry, _plan(additions=(addition,)))

        assert merged.get("workspace.export") == addition


class TestUpdateProjection:
    """An update replaces the existing package in the merged registry."""

    def test_update_projection(self):
        old_package = _make_package(decision=ACCEPT, title="Capability Accepted")
        registry = _registry(old_package)

        new_package = _make_package(
            decision=REVIEW,
            executable=False,
            title="Capability Requires Review",
            message="Projection requires manual review before execution.",
        )

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor()
        merged = executor.execute(registry, _plan(updates=(new_package,)))

        assert merged.get("workspace.bootstrap") == new_package


class TestMixedAddUpdate:
    """Additions, updates, and unchanged entries all land correctly."""

    def test_mixed_add_update(self):
        unchanged_package = _make_package(projection_name="session.actions")
        old_update_package = _make_package(
            projection_name="workspace.bootstrap",
            decision=ACCEPT,
        )
        registry = _registry(unchanged_package, old_update_package)

        new_update_package = _make_package(
            projection_name="workspace.bootstrap",
            decision=REVIEW,
            executable=False,
            title="Capability Requires Review",
            message="Projection requires manual review before execution.",
        )
        addition_package = _make_package(projection_name="workspace.export")

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor()
        merged = executor.execute(
            registry,
            _plan(
                additions=(addition_package,),
                updates=(new_update_package,),
                unchanged=(unchanged_package,),
            ),
        )

        assert merged.get("session.actions") == unchanged_package
        assert merged.get("workspace.bootstrap") == new_update_package
        assert merged.get("workspace.export") == addition_package
        assert merged.list_projection_names() == (
            "session.actions",
            "workspace.bootstrap",
            "workspace.export",
        )


class TestOriginalRegistryUnchanged:
    """Executing a merge never mutates the input registry."""

    def test_original_registry_unchanged(self):
        old_package = _make_package(decision=ACCEPT)
        registry = _registry(old_package)

        new_package = _make_package(decision=REVIEW, executable=False)
        addition_package = _make_package(projection_name="workspace.export")

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor()
        executor.execute(
            registry,
            _plan(updates=(new_package,), additions=(addition_package,)),
        )

        assert registry.list_projection_names() == ("workspace.bootstrap",)
        assert registry.get("workspace.bootstrap") == old_package


class TestNewRegistryContainsExpectedPackages:
    """The merged registry contains exactly the expected package set."""

    def test_new_registry_contains_expected_packages(self):
        unchanged_package = _make_package(projection_name="session.actions")
        registry = _registry(unchanged_package)

        addition_package = _make_package(projection_name="workspace.export")

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor()
        merged = executor.execute(
            registry,
            _plan(additions=(addition_package,), unchanged=(unchanged_package,)),
        )

        export = _export(merged)

        assert export.total_projections == 2
        assert export.packages == (unchanged_package, addition_package)


class TestRejectInvalidPlan:
    """None or wrong-type registry/plan values are rejected."""

    def test_reject_none_registry(self):
        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutionError
        ):
            executor.execute(None, _plan())

    def test_reject_none_plan(self):
        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutionError
        ):
            executor.execute(_registry(), None)

    def test_reject_non_plan_object(self):
        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutionError
        ):
            executor.execute(_registry(), object())


class TestRejectDuplicateProjections:
    """A plan with duplicate projection names is rejected, with no partial merge."""

    def test_reject_duplicate_projections(self):
        registry = _registry()
        first = _make_package(projection_name="workspace.bootstrap")
        second = _make_package(
            projection_name="workspace.bootstrap",
            decision=REVIEW,
            executable=False,
        )

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutionError
        ):
            executor.execute(
                registry,
                _plan(additions=(first,), updates=(second,)),
            )

        assert registry.list_projection_names() == ()


class TestDeterminism:
    """Executing the same merge twice produces equal registries."""

    def test_repeated_execution_is_deterministic(self):
        registry = _registry(_make_package(decision=ACCEPT))
        plan = _plan(
            updates=(_make_package(decision=REVIEW, executable=False),)
        )

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor()

        first = executor.execute(registry, plan)
        second = executor.execute(registry, plan)

        assert _export(first) == _export(second)


class TestImmutablePackagesPreserved:
    """Packages carried into the merged registry are the exact same objects."""

    def test_packages_are_preserved_by_identity(self):
        unchanged_package = _make_package(projection_name="session.actions")
        registry = _registry(unchanged_package)

        addition_package = _make_package(projection_name="workspace.export")

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutor()
        merged = executor.execute(
            registry,
            _plan(additions=(addition_package,), unchanged=(unchanged_package,)),
        )

        assert merged.get("session.actions") is unchanged_package
        assert merged.get("workspace.export") is addition_package
