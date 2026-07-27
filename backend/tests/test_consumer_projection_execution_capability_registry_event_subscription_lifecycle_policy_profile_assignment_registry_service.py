import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistrySnapshot,
)


def _build_assignment(target_id, profile_id, sequence=1):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment(
        assignment_id=f"{target_id}::{profile_id}::{sequence}",

        target_id=target_id,

        profile_id=profile_id,

        assigned_at=datetime.now(timezone.utc),
    )


def _build_service():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryService()


class TestRegisterAssignment:
    """An assignment can be registered and later found by target ID."""

    def test_register_assignment(self):
        service = _build_service()

        assignment = _build_assignment(
            "target-1",
            "profile-a",
        )

        service.register(assignment)

        assert service.find("target-1") is assignment
        assert service.contains("target-1") is True
        assert len(service.list()) == 1


class TestReplaceAssignment:
    """An existing assignment can be replaced while preserving insertion order."""

    def test_replace_assignment(self):
        service = _build_service()

        first = _build_assignment(
            "target-1",
            "profile-a",
            sequence=1,
        )

        second = _build_assignment(
            "target-1",
            "profile-b",
            sequence=2,
        )

        service.register(first)
        service.replace(second)

        assert service.find("target-1") is second
        assert service.find("target-1").profile_id == "profile-b"
        assert len(service.list()) == 1


class TestRemoveAssignment:
    """Removing an assignment deletes its entry from the registry."""

    def test_remove_assignment(self):
        service = _build_service()

        assignment = _build_assignment(
            "target-1",
            "profile-a",
        )

        service.register(assignment)
        service.remove("target-1")

        assert service.find("target-1") is None
        assert service.contains("target-1") is False
        assert len(service.list()) == 0


class TestLookupExistingAndMissing:
    """find() returns the assignment for a known target and None for an unknown one."""

    def test_lookup_existing(self):
        service = _build_service()

        assignment = _build_assignment(
            "target-1",
            "profile-a",
        )

        service.register(assignment)

        assert service.find("target-1") is assignment

    def test_lookup_missing(self):
        service = _build_service()

        assert service.find("target-1") is None


class TestContains:
    """contains() accurately reflects active registration state."""

    def test_contains_registered(self):
        service = _build_service()

        service.register(
            _build_assignment(
                "target-1",
                "profile-a",
            )
        )

        assert service.contains("target-1") is True

    def test_not_contains_unregistered(self):
        service = _build_service()

        assert service.contains("target-1") is False

    def test_not_contains_after_remove(self):
        service = _build_service()

        service.register(
            _build_assignment(
                "target-1",
                "profile-a",
            )
        )

        service.remove("target-1")

        assert service.contains("target-1") is False


class TestSnapshotGeneration:
    """snapshot() reflects the current active assignments at the moment it is taken."""

    def test_snapshot_empty(self):
        service = _build_service()

        snap = service.snapshot()

        assert isinstance(
            snap,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistrySnapshot,
        )
        assert snap.assignment_count == 0
        assert snap.target_ids == ()
        assert snap.profile_ids == ()

    def test_snapshot_with_assignments(self):
        service = _build_service()

        service.register(
            _build_assignment("target-a", "profile-x", sequence=1)
        )

        service.register(
            _build_assignment("target-b", "profile-y", sequence=2)
        )

        snap = service.snapshot()

        assert snap.assignment_count == 2
        assert snap.target_ids == ("target-a", "target-b")
        assert snap.profile_ids == ("profile-x", "profile-y")

    def test_snapshot_is_immutable(self):
        service = _build_service()

        service.register(
            _build_assignment("target-a", "profile-x")
        )

        snap = service.snapshot()

        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.assignment_count = 99

    def test_snapshot_reflects_state_at_call_time(self):
        service = _build_service()

        service.register(
            _build_assignment("target-a", "profile-x")
        )

        snap_before = service.snapshot()

        service.register(
            _build_assignment("target-b", "profile-y", sequence=2)
        )

        assert snap_before.assignment_count == 1
        assert service.snapshot().assignment_count == 2


class TestImmutableRegistry:
    """The registry is replaced atomically; list() returns a snapshot tuple."""

    def test_list_is_immutable_snapshot(self):
        service = _build_service()

        service.register(
            _build_assignment("target-1", "profile-a")
        )

        listed = service.list()

        service.register(
            _build_assignment("target-2", "profile-b", sequence=2)
        )

        assert len(listed) == 1
        assert len(service.list()) == 2

    def test_registry_replaced_not_mutated(self):
        service = _build_service()

        assignment = _build_assignment("target-1", "profile-a")
        service.register(assignment)

        registry_before = service._registry

        replacement = _build_assignment("target-1", "profile-b", sequence=2)
        service.replace(replacement)

        registry_after = service._registry

        assert registry_before is not registry_after
        assert registry_after.assignments["target-1"] is replacement


class TestRejectDuplicates:
    """register() rejects a target ID that is already registered."""

    def test_reject_duplicate_target_id(self):
        service = _build_service()

        service.register(
            _build_assignment("target-1", "profile-a")
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError
        ):
            service.register(
                _build_assignment("target-1", "profile-b", sequence=2)
            )


class TestValidationRejections:
    """None inputs and blank target/profile IDs are rejected with an error."""

    def test_reject_none_assignment(self):
        service = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError
        ):
            service.register(None)

    def test_reject_blank_target_id_in_assignment(self):
        service = _build_service()

        with pytest.raises(Exception):
            service.register(
                _build_assignment("   ", "profile-a")
            )

    def test_reject_replace_unknown_target(self):
        service = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError
        ):
            service.replace(
                _build_assignment("target-unknown", "profile-a")
            )

    def test_reject_remove_unknown_target(self):
        service = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError
        ):
            service.remove("target-unknown")

    def test_reject_remove_blank_target_id(self):
        service = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError
        ):
            service.remove("   ")


class TestInsertionOrder:
    """Assignments are listed in the order they were first registered."""

    def test_insertion_order_preserved(self):
        service = _build_service()

        a = _build_assignment("target-a", "profile-x", sequence=1)
        b = _build_assignment("target-b", "profile-y", sequence=2)
        c = _build_assignment("target-c", "profile-z", sequence=3)

        service.register(a)
        service.register(b)
        service.register(c)

        listed = service.list()

        assert listed[0] is a
        assert listed[1] is b
        assert listed[2] is c

    def test_replace_preserves_insertion_order(self):
        service = _build_service()

        a = _build_assignment("target-a", "profile-x", sequence=1)
        b = _build_assignment("target-b", "profile-y", sequence=2)

        service.register(a)
        service.register(b)

        replacement = _build_assignment("target-a", "profile-updated", sequence=3)
        service.replace(replacement)

        listed = service.list()

        assert listed[0] is replacement
        assert listed[1] is b
