import dataclasses

from datetime import datetime, timezone

from types import MappingProxyType

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationPlan,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService,
)


def _build_profile(profile_id="development", policy_identifiers=("policy-a",)):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,

        profile_name=profile_id,

        description=f"Profile {profile_id}.",

        policy_identifiers=policy_identifiers,
    )


def _build_version(version_id, policy_identifiers):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion(
        version=version_id,

        policy_identifiers=policy_identifiers,

        created_at=datetime.now(timezone.utc),
    )


def _build_service(profile_id="development", versions=(("1.0.0", ("policy-a",)), ("1.1.0", ("policy-a", "policy-b"))), steps=None):
    registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
    registry.register(
        _build_profile(
            profile_id
        )
    )

    version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()

    for version_id, policy_identifiers in versions:

        version_service.publish(

            profile_id,

            _build_version(

                version_id,

                policy_identifiers,
            ),
        )

    resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
        registry
    )

    compatibility_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityService(
        resolver,

        version_service,
    )

    migration_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationService(
        resolver,

        version_service,

        compatibility_service,

        steps=steps,
    )

    return migration_service, registry, version_service


class TestCreateMigrationPlan:
    """plan() builds a deterministic plan between two distinct versions."""

    def test_create_migration_plan(self):
        service, _, _ = _build_service()

        plan = service.plan(
            "development",

            "1.0.0",

            "1.1.0",
        )

        assert isinstance(
            plan,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationPlan,
        )
        assert plan.profile_id == "development"
        assert plan.source_version == "1.0.0"
        assert plan.target_version == "1.1.0"
        assert len(plan.migration_steps) == 1

        other_plan = service.plan(
            "development",

            "1.0.0",

            "1.1.0",
        )

        assert len(other_plan.migration_steps) == len(plan.migration_steps)


class TestMigrateSuccessfully:
    """migrate() produces a new profile instance carrying the target version's configuration."""

    def test_migrate_successfully(self):
        service, _, _ = _build_service()

        result = service.migrate(
            "development",

            "1.0.0",

            "1.1.0",
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationResult,
        )
        assert result.successful is True
        assert result.source_version == "1.0.0"
        assert result.target_version == "1.1.0"
        assert result.migrated_profile.version == "1.1.0"
        assert result.migrated_profile.policy_identifiers == ("policy-a", "policy-b")


class TestPreserveParameterValues:
    """A migration step preserves an instance's parameter values, only changing version and policy identifiers."""

    def test_preserve_parameter_values(self):
        service, _, _ = _build_service()

        plan = service.plan(
            "development",

            "1.0.0",

            "1.1.0",
        )

        starting_instance = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance(
            profile_id="development",

            version="1.0.0",

            policy_identifiers=("policy-a",),

            parameter_values=MappingProxyType(
                {
                    "threshold": 5,
                }
            ),
        )

        migrated_instance = plan.migration_steps[0](
            starting_instance
        )

        assert migrated_instance.version == "1.1.0"
        assert migrated_instance.policy_identifiers == ("policy-a", "policy-b")
        assert dict(migrated_instance.parameter_values) == {"threshold": 5}


class TestNoOpMigration:
    """Migrating between identical versions succeeds without applying any steps."""

    def test_no_op_migration(self):
        service, _, _ = _build_service()

        plan = service.plan(
            "development",

            "1.0.0",

            "1.0.0",
        )

        assert plan.migration_steps == ()

        result = service.migrate(
            "development",

            "1.0.0",

            "1.0.0",
        )

        assert result.successful is True
        assert result.migrated_profile.version == "1.0.0"
        assert result.migrated_profile.policy_identifiers == ("policy-a",)


class TestCanMigrateTrue:
    """can_migrate() reports True for a compatible, published version pair, and for a no-op."""

    def test_can_migrate_true_distinct_versions(self):
        service, _, _ = _build_service()

        assert service.can_migrate(
            "development",

            "1.0.0",

            "1.1.0",
        ) is True

    def test_can_migrate_true_no_op(self):
        service, _, _ = _build_service()

        assert service.can_migrate(
            "development",

            "1.0.0",

            "1.0.0",
        ) is True


class TestCanMigrateFalse:
    """can_migrate() reports False without raising for nonexistent profiles or versions."""

    def test_can_migrate_false_missing_profile(self):
        service, _, _ = _build_service()

        assert service.can_migrate(
            "does-not-exist",

            "1.0.0",

            "1.1.0",
        ) is False

    def test_can_migrate_false_missing_target_version(self):
        service, _, _ = _build_service()

        assert service.can_migrate(
            "development",

            "1.0.0",

            "9.9.9",
        ) is False

    def test_can_migrate_false_incompatible_target(self):
        service, _, _ = _build_service(
            versions=(
                ("1.0.0", ("policy-a",)),

                ("2.0.0", ()),
            ),
        )

        assert service.can_migrate(
            "development",

            "1.0.0",

            "2.0.0",
        ) is False


class TestImmutableMigrationResult:
    """A migration result and its migrated profile cannot be reassigned."""

    def test_immutable_migration_result(self):
        service, _, _ = _build_service()

        result = service.migrate(
            "development",

            "1.0.0",

            "1.1.0",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.successful = False

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.migrated_profile.version = "9.9.9"

    def test_does_not_mutate_historical_versions(self):
        service, _, version_service = _build_service()

        service.migrate(
            "development",

            "1.0.0",

            "1.1.0",
        )

        assert version_service.find("development", "1.0.0").policy_identifiers == ("policy-a",)
        assert version_service.find("development", "1.1.0").policy_identifiers == ("policy-a", "policy-b")


class TestRejectInvalidMigrationRequests:
    """None inputs, blank identifiers, missing versions, incompatible paths, and duplicate steps are rejected."""

    def test_reject_none_profile_id(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError
        ):
            service.plan(None, "1.0.0", "1.1.0")

    def test_reject_blank_profile_id(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError
        ):
            service.plan("   ", "1.0.0", "1.1.0")

    def test_reject_missing_source_version(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError
        ):
            service.plan("development", "9.9.9", "1.1.0")

    def test_reject_missing_target_version(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError
        ):
            service.plan("development", "1.0.0", "9.9.9")

    def test_reject_nonexistent_profile(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError
        ):
            service.migrate("does-not-exist", "1.0.0", "1.1.0")

    def test_reject_incompatible_migration_path(self):
        service, _, _ = _build_service(
            versions=(
                ("1.0.0", ("policy-a",)),

                ("2.0.0", ()),
            ),
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError
        ):
            service.migrate("development", "1.0.0", "2.0.0")

    def test_reject_duplicate_migration_steps(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileMigrationError
        ):
            _build_service(
                steps=[
                    (("1.0.0", "1.1.0"), lambda instance: instance),
                    (("1.0.0", "1.1.0"), lambda instance: instance),
                ],
            )
