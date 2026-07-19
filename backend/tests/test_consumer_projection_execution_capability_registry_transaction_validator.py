import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransaction,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionEntry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator,
)


ACCEPT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT

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


def _entry(operation, package):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionEntry(
        operation=operation,
        package=package,
    )


def _transaction(*entries):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransaction(
        entries=tuple(entries),
    )


class TestEmptyTransaction:
    """An empty transaction validates as trivially valid."""

    def test_empty_transaction(self):
        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()

        report = validator.validate(_transaction())

        assert report.total_operations == 0
        assert report.register_operations == 0
        assert report.update_operations == 0
        assert report.remove_operations == 0
        assert report.duplicate_projection_names == ()
        assert report.is_valid is True


class TestValidTransaction:
    """A transaction with unique, well-formed entries is valid."""

    def test_valid_transaction(self):
        register_entry = _entry(
            REGISTER, _make_package(projection_name="workspace.export")
        )
        update_entry = _entry(
            UPDATE, _make_package(projection_name="workspace.bootstrap")
        )
        remove_entry = _entry(
            REMOVE, _make_package(projection_name="workspace.attention")
        )

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()
        report = validator.validate(
            _transaction(register_entry, update_entry, remove_entry)
        )

        assert report.total_operations == 3
        assert report.register_operations == 1
        assert report.update_operations == 1
        assert report.remove_operations == 1
        assert report.duplicate_projection_names == ()
        assert report.is_valid is True


class TestDuplicateProjection:
    """Two entries targeting the same projection are flagged as duplicates."""

    def test_duplicate_projection(self):
        first = _entry(
            REGISTER, _make_package(projection_name="workspace.bootstrap")
        )
        second = _entry(
            UPDATE, _make_package(projection_name="workspace.bootstrap")
        )

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()
        report = validator.validate(_transaction(first, second))

        assert report.duplicate_projection_names == ("workspace.bootstrap",)
        assert report.is_valid is False


class TestInvalidOperation:
    """An entry with an operation that is not a valid enum member is invalid."""

    def test_invalid_operation(self):
        entry = _entry("delete", _make_package())

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()
        report = validator.validate(_transaction(entry))

        assert report.total_operations == 1
        assert report.register_operations == 0
        assert report.update_operations == 0
        assert report.remove_operations == 0
        assert report.duplicate_projection_names == ("workspace.bootstrap",)
        assert report.is_valid is False


class TestEmptyProjectionName:
    """An entry with an empty projection name is invalid."""

    def test_empty_projection_name(self):
        entry = _entry(REGISTER, _make_package(projection_name=""))

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()
        report = validator.validate(_transaction(entry))

        assert report.duplicate_projection_names == ("",)
        assert report.is_valid is False


class TestOperationCounts:
    """Operation counts are accurate across a mixed transaction."""

    def test_correct_operation_counts(self):
        entries = (
            _entry(REGISTER, _make_package(projection_name="a")),
            _entry(REGISTER, _make_package(projection_name="b")),
            _entry(UPDATE, _make_package(projection_name="c")),
            _entry(REMOVE, _make_package(projection_name="d")),
        )

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()
        report = validator.validate(_transaction(*entries))

        assert report.total_operations == 4
        assert report.register_operations == 2
        assert report.update_operations == 1
        assert report.remove_operations == 1


class TestDuplicateDetection:
    """Duplicate detection correctly separates safe entries from unsafe ones."""

    def test_correct_duplicate_detection(self):
        safe = _entry(REGISTER, _make_package(projection_name="workspace.export"))
        dup_one = _entry(
            UPDATE, _make_package(projection_name="workspace.bootstrap")
        )
        dup_two = _entry(
            REMOVE, _make_package(projection_name="workspace.bootstrap")
        )

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()
        report = validator.validate(_transaction(safe, dup_one, dup_two))

        assert report.duplicate_projection_names == ("workspace.bootstrap",)


class TestValidityFlag:
    """is_valid tracks the presence of unsafe projection names exactly."""

    def test_is_valid_true_without_problems(self):
        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()

        report = validator.validate(
            _transaction(_entry(REGISTER, _make_package()))
        )

        assert report.is_valid is True

    def test_is_valid_false_with_problems(self):
        first = _entry(REGISTER, _make_package(projection_name="workspace.bootstrap"))
        second = _entry(UPDATE, _make_package(projection_name="workspace.bootstrap"))

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()
        report = validator.validate(_transaction(first, second))

        assert report.is_valid is False


class TestTransactionUnchanged:
    """Validation never mutates the transaction or its entries."""

    def test_transaction_remains_unchanged(self):
        package = _make_package()
        entry = _entry(REGISTER, package)
        transaction = _transaction(entry)
        package_dict = package.to_dict()

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()
        validator.validate(transaction)

        assert transaction.entries == (entry,)
        assert package.to_dict() == package_dict


class TestInvalidTransaction:
    """A None or non-transaction value is rejected."""

    def test_reject_none_transaction(self):
        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationError
        ):
            validator.validate(None)

    def test_reject_non_transaction_object(self):
        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationError
        ):
            validator.validate(object())


class TestDeterminism:
    """Validating the same transaction twice agrees."""

    def test_repeated_validation_is_deterministic(self):
        transaction = _transaction(_entry(REGISTER, _make_package()))
        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator()

        first = validator.validate(transaction)
        second = validator.validate(transaction)

        assert first == second
