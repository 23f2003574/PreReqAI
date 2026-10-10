import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService,
)


def _build_profile(profile_id, policy_identifiers=("policy-a", "policy-b")):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,

        profile_name=profile_id,

        description=f"Profile {profile_id}.",

        policy_identifiers=policy_identifiers,
    )


def _build_service(profile_ids=("development",)):
    profile_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

    for profile_id in profile_ids:

        profile_service.register(
            _build_profile(
                profile_id
            )
        )

    assignment_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentService(
        profile_service
    )

    return assignment_service, profile_service


class TestAssignProfile:
    """A profile can be assigned to a target and later found."""

    def test_assign_profile(self):
        service, _ = _build_service()

        result = service.assign(
            "capability-1",

            "development",
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResult,
        )
        assert result.successful is True
        assert result.assignment.target_id == "capability-1"
        assert result.assignment.profile_id == "development"
        assert service.find("capability-1") is result.assignment
        assert service.is_assigned("capability-1") is True


class TestReplaceAssignment:
    """Assigning a different profile replaces the active mapping only."""

    def test_replace_assignment(self):
        service, _ = _build_service(
            profile_ids=("development", "staging"),
        )

        first = service.assign(
            "capability-1",

            "development",
        )

        second = service.assign(
            "capability-1",

            "staging",
        )

        assert service.find("capability-1") is second.assignment
        assert service.find("capability-1").profile_id == "staging"
        assert service.is_assigned("capability-1") is True
        assert len(service.list()) == 2
        assert service.list()[0] is first.assignment
        assert service.list()[1] is second.assignment


class TestUnassign:
    """Unassigning removes the active mapping for a target."""

    def test_unassign(self):
        service, _ = _build_service()

        assigned = service.assign(
            "capability-1",

            "development",
        )

        result = service.unassign(
            "capability-1"
        )

        assert result.successful is True
        assert result.assignment is assigned.assignment
        assert service.find("capability-1") is None
        assert service.is_assigned("capability-1") is False
        assert len(service.list()) == 1


class TestLookupAssignment:
    """An active assignment is found by find()."""

    def test_lookup_assignment(self):
        service, _ = _build_service()

        assigned = service.assign(
            "subscription-1",

            "development",
        )

        assert service.find("subscription-1") is assigned.assignment


class TestListAssignments:
    """Assignments are listed in creation order."""

    def test_list_assignments(self):
        service, _ = _build_service(
            profile_ids=("alpha", "beta"),
        )

        first = service.assign(
            "target-a",

            "alpha",
        )

        second = service.assign(
            "target-b",

            "beta",
        )

        assert [
            assignment.target_id
            for assignment in service.list()
        ] == ["target-a", "target-b"]
        assert service.list()[0] is first.assignment
        assert service.list()[1] is second.assignment


class TestAssignmentExistence:
    """is_assigned() reports active assignment state accurately."""

    def test_assignment_existence(self):
        service, _ = _build_service()

        assert service.is_assigned("capability-1") is False

        service.assign(
            "capability-1",

            "development",
        )

        assert service.is_assigned("capability-1") is True
        assert service.is_assigned("capability-2") is False


class TestRejectInvalidInputs:
    """Invalid IDs, unknown profiles, and duplicate assignments are rejected."""

    def test_reject_blank_target_id(self):
        service, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError
        ):
            service.assign(
                "   ",

                "development",
            )

    def test_reject_blank_profile_id(self):
        service, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError
        ):
            service.assign(
                "capability-1",

                "   ",
            )

    def test_reject_unknown_profile(self):
        service, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError
        ):
            service.assign(
                "capability-1",

                "does-not-exist",
            )

    def test_reject_duplicate_active_assignment(self):
        service, _ = _build_service()

        service.assign(
            "capability-1",

            "development",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError
        ):
            service.assign(
                "capability-1",

                "development",
            )

    def test_reject_unassign_when_not_assigned(self):
        service, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError
        ):
            service.unassign(
                "capability-1"
            )

    def test_reject_unassign_blank_target_id(self):
        service, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError
        ):
            service.unassign(
                "   "
            )


class TestImmutableResults:
    """Returned assignment results and records cannot be reassigned."""

    def test_immutable_results(self):
        service, _ = _build_service()

        result = service.assign(
            "capability-1",

            "development",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.successful = False

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.assignment.profile_id = "other"

    def test_immutable_list_snapshot(self):
        service, _ = _build_service()

        service.assign(
            "capability-1",

            "development",
        )

        listed = service.list()

        service.assign(
            "capability-2",

            "development",
        )

        assert len(listed) == 1
        assert len(service.list()) == 2
