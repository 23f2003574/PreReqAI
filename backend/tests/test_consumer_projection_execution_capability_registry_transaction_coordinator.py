import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransaction,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinator,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinatorError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionEntry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationReport,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator,
)


ACCEPT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT
REGISTER = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation.REGISTER


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


def _entry(operation, package):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionEntry(
        operation=operation,
        package=package,
    )


def _transaction(*entries):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransaction(
        entries=tuple(entries),
    )


def _registry(*packages):
    registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()

    for package in packages:
        registry.register(package)

    return registry


def _export(registry):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExporter().export(
        registry
    )


def _valid_report():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationReport(
        total_operations=1,
        register_operations=1,
        update_operations=0,
        remove_operations=0,
        duplicate_projection_names=(),
        is_valid=True,
    )


def _invalid_report():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationReport(
        total_operations=1,
        register_operations=1,
        update_operations=0,
        remove_operations=0,
        duplicate_projection_names=("workspace.bootstrap",),
        is_valid=False,
    )


class _SpyValidator:
    """Records validate() calls and delegates to a real validator."""

    def __init__(self, calls, report=None):
        self._calls = calls
        self._report = report
        self.call_count = 0

    def validate(self, transaction):
        self.call_count += 1
        self._calls.append("validate")

        if self._report is not None:
            return self._report

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator().validate(
            transaction
        )


class _SpyExecutor:
    """Records execute() calls and delegates to a real executor."""

    def __init__(self, calls, error=None):
        self._calls = calls
        self._error = error
        self.call_count = 0

    def execute(self, registry, transaction):
        self.call_count += 1
        self._calls.append("execute")

        if self._error is not None:
            raise self._error

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor().execute(
            registry, transaction
        )


class _RaisingValidator:
    def validate(self, transaction):
        raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationError(
            "malformed transaction"
        )


class TestSuccessfulCoordination:
    """A valid transaction is validated and then executed."""

    def test_successful_coordination(self):
        registry = _registry()
        transaction = _transaction(
            _entry(REGISTER, _make_package(projection_name="workspace.export"))
        )

        coordinator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinator(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator(),
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor(),
        )

        updated = coordinator.coordinate(registry, transaction)

        assert updated.get("workspace.export") is not None


class TestValidatorInvokedBeforeExecutor:
    """The validator runs before the executor, in that order."""

    def test_validator_invoked_before_executor(self):
        calls = []
        registry = _registry()
        transaction = _transaction(
            _entry(REGISTER, _make_package(projection_name="workspace.export"))
        )

        coordinator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinator(
            _SpyValidator(calls),
            _SpyExecutor(calls),
        )

        coordinator.coordinate(registry, transaction)

        assert calls == ["validate", "execute"]


class TestExecutorSkippedOnValidationFailure:
    """When validation fails, the executor is never invoked."""

    def test_executor_skipped_on_validation_failure(self):
        calls = []
        registry = _registry()
        transaction = _transaction(
            _entry(REGISTER, _make_package(projection_name="workspace.bootstrap"))
        )

        validator = _SpyValidator(calls, report=_invalid_report())
        executor = _SpyExecutor(calls)

        coordinator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinator(
            validator,
            executor,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinatorError
        ):
            coordinator.coordinate(registry, transaction)

        assert executor.call_count == 0
        assert calls == ["validate"]


class TestValidationErrorPropagated:
    """A validation-side error propagates unchanged, unwrapped."""

    def test_validation_error_propagated(self):
        registry = _registry()
        transaction = _transaction()

        coordinator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinator(
            _RaisingValidator(),
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor(),
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationError
        ):
            coordinator.coordinate(registry, transaction)


class TestExecutionErrorPropagated:
    """An execution-side error propagates unchanged, unwrapped."""

    def test_execution_error_propagated(self):
        calls = []
        registry = _registry()
        transaction = _transaction(
            _entry(REGISTER, _make_package(projection_name="workspace.export"))
        )

        error = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError(
            "execution blew up"
        )
        validator = _SpyValidator(calls, report=_valid_report())
        executor = _SpyExecutor(calls, error=error)

        coordinator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinator(
            validator,
            executor,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError
        ) as excinfo:
            coordinator.coordinate(registry, transaction)

        assert excinfo.value is error


class TestUpdatedRegistryReturned:
    """coordinate() returns the registry produced by the executor."""

    def test_updated_registry_returned(self):
        registry = _registry()
        addition = _make_package(projection_name="workspace.export")
        transaction = _transaction(_entry(REGISTER, addition))

        coordinator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinator(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator(),
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor(),
        )

        updated = coordinator.coordinate(registry, transaction)
        export = _export(updated)

        assert export.total_projections == 1
        assert export.packages == (addition,)


class TestOriginalRegistryUnchanged:
    """Coordinating a transaction never mutates the input registry."""

    def test_original_registry_unchanged(self):
        package = _make_package()
        registry = _registry(package)
        transaction = _transaction(
            _entry(REGISTER, _make_package(projection_name="workspace.export"))
        )

        coordinator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinator(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator(),
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor(),
        )

        coordinator.coordinate(registry, transaction)

        assert registry.list_projection_names() == ("workspace.bootstrap",)
        assert registry.get("workspace.bootstrap") == package


class TestDependenciesInvokedExactlyOnce:
    """Both collaborators are invoked exactly once on a successful run."""

    def test_dependencies_invoked_exactly_once(self):
        calls = []
        registry = _registry()
        transaction = _transaction(
            _entry(REGISTER, _make_package(projection_name="workspace.export"))
        )

        validator = _SpyValidator(calls)
        executor = _SpyExecutor(calls)

        coordinator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinator(
            validator,
            executor,
        )

        coordinator.coordinate(registry, transaction)

        assert validator.call_count == 1
        assert executor.call_count == 1


class TestDeterminism:
    """Coordinating the same registry and transaction twice agrees."""

    def test_repeated_coordination_is_deterministic(self):
        registry = _registry()
        transaction = _transaction(
            _entry(REGISTER, _make_package(projection_name="workspace.export"))
        )

        coordinator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinator(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator(),
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor(),
        )

        first = coordinator.coordinate(registry, transaction)
        second = coordinator.coordinate(registry, transaction)

        assert _export(first) == _export(second)


class TestNoBusinessLogicInsideCoordinator:
    """The coordinator holds only its two injected collaborators."""

    def test_coordinator_holds_only_its_dependencies(self):
        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()
        executor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor()

        coordinator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinator(
            validator,
            executor,
        )

        assert coordinator.__dict__ == {
            "_validator": validator,
            "_executor": executor,
        }
