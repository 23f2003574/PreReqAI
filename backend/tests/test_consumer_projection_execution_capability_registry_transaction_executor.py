import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransaction,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionEntry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation,
)


ACCEPT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT
REVIEW = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REVIEW

REGISTER = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation.REGISTER
UPDATE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation.UPDATE
REMOVE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation.REMOVE


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


def _entry(operation, package):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionEntry(
        operation=operation,
        package=package,
    )


def _transaction(*entries):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransaction(
        entries=tuple(entries),
    )


def _export(registry):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter().export(
        registry
    )


class TestEmptyTransaction:
    """An empty transaction leaves the registry contents equivalent."""

    def test_empty_transaction(self):
        package = _make_package()
        registry = _registry(package)

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()
        updated = executor.execute(registry, _transaction())

        assert _export(updated) == _export(registry)


class TestRegisterOperation:
    """REGISTER adds a new projection."""

    def test_register_operation(self):
        registry = _registry()
        package = _make_package(projection_name="workspace.export")

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()
        updated = executor.execute(
            registry,
            _transaction(_entry(REGISTER, package)),
        )

        assert updated.get("workspace.export") == package


class TestUpdateOperation:
    """UPDATE replaces an existing projection."""

    def test_update_operation(self):
        old_package = _make_package(decision=ACCEPT)
        registry = _registry(old_package)

        new_package = _make_package(decision=REVIEW, executable=False)

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()
        updated = executor.execute(
            registry,
            _transaction(_entry(UPDATE, new_package)),
        )

        assert updated.get("workspace.bootstrap") == new_package


class TestRemoveOperation:
    """REMOVE deletes an existing projection."""

    def test_remove_operation(self):
        package = _make_package()
        registry = _registry(package)

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()
        updated = executor.execute(
            registry,
            _transaction(_entry(REMOVE, package)),
        )

        assert updated.contains("workspace.bootstrap") is False
        assert updated.list_projection_names() == ()


class TestMixedTransaction:
    """REGISTER, UPDATE, and REMOVE can all appear in one transaction."""

    def test_mixed_transaction(self):
        removed_package = _make_package(projection_name="workspace.attention")
        old_updated_package = _make_package(
            projection_name="workspace.bootstrap",
            decision=ACCEPT,
        )
        registry = _registry(removed_package, old_updated_package)

        new_updated_package = _make_package(
            projection_name="workspace.bootstrap",
            decision=REVIEW,
            executable=False,
        )
        registered_package = _make_package(projection_name="workspace.export")

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()
        updated = executor.execute(
            registry,
            _transaction(
                _entry(REMOVE, removed_package),
                _entry(UPDATE, new_updated_package),
                _entry(REGISTER, registered_package),
            ),
        )

        assert updated.contains("workspace.attention") is False
        assert updated.get("workspace.bootstrap") == new_updated_package
        assert updated.get("workspace.export") == registered_package
        assert updated.list_projection_names() == (
            "workspace.bootstrap",
            "workspace.export",
        )


class TestAtomicRollbackOnFailure:
    """If any entry fails, no entry is applied."""

    def test_atomic_rollback_on_failure(self):
        registry = _registry()
        registered_package = _make_package(projection_name="workspace.export")
        bad_update_package = _make_package(projection_name="workspace.bootstrap")

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError
        ):
            executor.execute(
                registry,
                _transaction(
                    _entry(REGISTER, registered_package),
                    _entry(UPDATE, bad_update_package),
                ),
            )


class TestOriginalRegistryUnchanged:
    """Executing a transaction never mutates the input registry."""

    def test_original_registry_unchanged(self):
        package = _make_package()
        registry = _registry(package)

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()
        executor.execute(
            registry,
            _transaction(_entry(REMOVE, package)),
        )

        assert registry.list_projection_names() == ("workspace.bootstrap",)
        assert registry.get("workspace.bootstrap") == package


class TestRejectConflictingOperations:
    """Two entries targeting the same projection are rejected."""

    def test_reject_conflicting_operations(self):
        registry = _registry()
        first = _make_package(projection_name="workspace.bootstrap")
        second = _make_package(
            projection_name="workspace.bootstrap",
            decision=REVIEW,
            executable=False,
        )

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError
        ):
            executor.execute(
                registry,
                _transaction(
                    _entry(REGISTER, first),
                    _entry(REGISTER, second),
                ),
            )

        assert registry.list_projection_names() == ()

    def test_reject_none_registry(self):
        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError
        ):
            executor.execute(None, _transaction())

    def test_reject_none_transaction(self):
        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError
        ):
            executor.execute(_registry(), None)

    def test_reject_empty_projection_name(self):
        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()
        package = _make_package(projection_name="")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError
        ):
            executor.execute(
                _registry(),
                _transaction(_entry(REGISTER, package)),
            )


class TestDeterminism:
    """Executing the same transaction twice produces equal registries."""

    def test_repeated_execution_is_deterministic(self):
        registry = _registry(_make_package(decision=ACCEPT))
        transaction = _transaction(
            _entry(
                UPDATE,
                _make_package(decision=REVIEW, executable=False),
            )
        )

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()

        first = executor.execute(registry, transaction)
        second = executor.execute(registry, transaction)

        assert _export(first) == _export(second)


class TestImmutablePackagesPreserved:
    """Packages carried into the updated registry are the exact same objects."""

    def test_packages_preserved_by_identity(self):
        registry = _registry()
        package = _make_package(projection_name="workspace.export")

        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()
        updated = executor.execute(
            registry,
            _transaction(_entry(REGISTER, package)),
        )

        assert updated.get("workspace.export") is package
