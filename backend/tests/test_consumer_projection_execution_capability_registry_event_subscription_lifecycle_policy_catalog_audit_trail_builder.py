from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditEntry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditOperation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrail,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError,
)


CREATED = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditOperation.CREATED
POLICY_ADDED = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditOperation.POLICY_ADDED
POLICY_UPDATED = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditOperation.POLICY_UPDATED


def _entry(sequence_number, operation=CREATED, policy_identifier=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditEntry(
        sequence_number=sequence_number,

        operation=operation,

        policy_identifier=policy_identifier,

        timestamp=datetime.now(timezone.utc),
    )


class TestEmptyAuditTrail:
    """An audit trail can be built with no entries."""

    def test_empty_audit_trail(self):
        audit_trail = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder().build(
            ()
        )

        assert isinstance(
            audit_trail,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrail,
        )
        assert audit_trail.entries == ()
        assert audit_trail.total_entries == 0


class TestAppendSingleEntry:
    """An entry can be appended to an empty audit trail."""

    def test_append_single_entry(self):
        audit_trail = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder().build(
            ()
        )

        entry = _entry(1)

        updated_audit_trail = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder().append(
            audit_trail,

            entry,
        )

        assert updated_audit_trail.entries == (entry,)
        assert updated_audit_trail.total_entries == 1


class TestAppendMultipleEntries:
    """Multiple entries can be appended in sequence."""

    def test_append_multiple_entries(self):
        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder()

        audit_trail = builder.build(())

        audit_trail = builder.append(
            audit_trail,

            _entry(1, POLICY_ADDED, "policy-a"),
        )
        audit_trail = builder.append(
            audit_trail,

            _entry(2, POLICY_UPDATED, "policy-a"),
        )

        assert audit_trail.total_entries == 2
        assert [
            entry.sequence_number

            for entry in audit_trail.entries
        ] == [1, 2]


class TestSequenceOrderingPreserved:
    """build() preserves the insertion order of its entries."""

    def test_sequence_ordering_preserved(self):
        entries = (
            _entry(1),
            _entry(2),
            _entry(3),
        )

        audit_trail = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder().build(
            entries
        )

        assert audit_trail.entries == entries


class TestTotalEntriesUpdated:
    """total_entries reflects the current number of entries after each append."""

    def test_total_entries_updated(self):
        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder()

        audit_trail = builder.build(
            (
                _entry(1),
            )
        )

        assert audit_trail.total_entries == 1

        audit_trail = builder.append(
            audit_trail,

            _entry(2),
        )

        assert audit_trail.total_entries == 2


class TestImmutableAppend:
    """Appending returns a new audit trail without mutating the original."""

    def test_immutable_append(self):
        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder()

        original = builder.build(
            (
                _entry(1),
            )
        )

        updated = builder.append(
            original,

            _entry(2),
        )

        assert original.total_entries == 1
        assert updated.total_entries == 2
        assert original is not updated
        assert original.entries != updated.entries


class TestRejectDuplicateSequenceNumbers:
    """Duplicate sequence numbers are rejected."""

    def test_reject_duplicate_sequence_numbers(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder().build(
                (
                    _entry(1),
                    _entry(1),
                )
            )

    def test_reject_duplicate_sequence_number_on_append(self):
        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder()

        audit_trail = builder.build(
            (
                _entry(1),
            )
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError
        ):
            builder.append(
                audit_trail,

                _entry(1),
            )


class TestRejectInvalidEntries:
    """None inputs, out-of-order sequence numbers, invalid operations, and missing timestamps are rejected."""

    def test_reject_none_entries_on_build(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder().build(
                None
            )

    def test_reject_none_entry_within_collection(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder().build(
                (
                    _entry(1),
                    None,
                )
            )

    def test_reject_none_audit_trail_on_append(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder().append(
                None,

                _entry(1),
            )

    def test_reject_none_entry_on_append(self):
        audit_trail = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder().build(
            ()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder().append(
                audit_trail,

                None,
            )

    def test_reject_out_of_order_sequence_number(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder().build(
                (
                    _entry(2),
                    _entry(1),
                )
            )

    def test_reject_invalid_operation(self):
        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditEntry(
            sequence_number=1,

            operation="created",

            policy_identifier=None,

            timestamp=datetime.now(timezone.utc),
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder().build(
                (
                    entry,
                )
            )

    def test_reject_missing_timestamp(self):
        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditEntry(
            sequence_number=1,

            operation=CREATED,

            policy_identifier=None,

            timestamp=None,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogAuditTrailBuilder().build(
                (
                    entry,
                )
            )
