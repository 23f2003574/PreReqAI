import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationPlan,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService,
)


_STATE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState


def _build_policy(allowed_states, initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        allowed_states,

        initial_state,
    )


def _build_template():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
        template_id="standard-registration",

        template_name="Standard Registration",

        description="A standard registration lifecycle policy.",

        lifecycle_policy=_build_policy(
            (_STATE.REGISTERED, _STATE.ACTIVE),

            _STATE.REGISTERED,
        ),
    )


def _add_suspended(policy):

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy(
        allowed_states=policy.allowed_states + (_STATE.SUSPENDED,),

        initial_state=policy.initial_state,
    )


def _add_unregistered(policy):

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy(
        allowed_states=policy.allowed_states + (_STATE.UNREGISTERED,),

        initial_state=policy.initial_state,
    )


class TestValidMigration:
    """A single registered step migrates the policy directly."""

    def test_valid_migration(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService(
            steps={
                ("1.0.0", "1.1.0"): _add_suspended,
            },
        )
        template = _build_template()

        plan = service.plan(
            template,

            "1.0.0",

            "1.1.0",
        )

        assert isinstance(
            plan,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationPlan,
        )
        assert plan.migration_steps == (_add_suspended,)

        source_policy = template.lifecycle_policy

        result = service.migrate(
            source_policy,

            plan,
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationResult,
        )
        assert result.migration_successful is True
        assert result.source_version == "1.0.0"
        assert result.target_version == "1.1.0"
        assert _STATE.SUSPENDED in result.migrated_policy.allowed_states
        assert _STATE.SUSPENDED not in source_policy.allowed_states


class TestMultiStepMigration:
    """Multiple hops are applied sequentially in order."""

    def test_multi_step_migration(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService(
            steps={
                ("1.0.0", "1.1.0"): _add_suspended,

                ("1.1.0", "2.0.0"): _add_unregistered,
            },
        )
        template = _build_template()

        plan = service.plan(
            template,

            "1.0.0",

            "2.0.0",
        )

        assert plan.migration_steps == (
            _add_suspended,

            _add_unregistered,
        )

        result = service.migrate(
            template.lifecycle_policy,

            plan,
        )

        assert result.migration_successful is True
        assert _STATE.SUSPENDED in result.migrated_policy.allowed_states
        assert _STATE.UNREGISTERED in result.migrated_policy.allowed_states


class TestUnsupportedMigration:
    """A version pair with no registered path is rejected."""

    def test_unsupported_migration(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService(
            steps={
                ("1.0.0", "1.1.0"): _add_suspended,
            },
        )
        template = _build_template()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError
        ):
            service.plan(
                template,

                "1.0.0",

                "9.9.9",
            )


class TestIdenticalVersions:
    """Planning a migration between identical versions is rejected."""

    def test_identical_versions(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService()
        template = _build_template()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError
        ):
            service.plan(
                template,

                "1.0.0",

                "1.0.0",
            )


class TestCanMigrate:
    """can_migrate() reports whether a path exists, without raising."""

    def test_can_migrate_true(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService(
            steps={
                ("1.0.0", "1.1.0"): _add_suspended,

                ("1.1.0", "2.0.0"): _add_unregistered,
            },
        )

        assert service.can_migrate("1.0.0", "1.1.0") is True
        assert service.can_migrate("1.0.0", "2.0.0") is True

    def test_can_migrate_false(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService(
            steps={
                ("1.0.0", "1.1.0"): _add_suspended,
            },
        )

        assert service.can_migrate("1.0.0", "9.9.9") is False
        assert service.can_migrate("1.0.0", "1.0.0") is False


class TestImmutableSourcePolicy:
    """Migration never modifies the source lifecycle policy."""

    def test_immutable_source_policy(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService(
            steps={
                ("1.0.0", "1.1.0"): _add_suspended,
            },
        )
        template = _build_template()
        plan = service.plan(
            template,

            "1.0.0",

            "1.1.0",
        )
        source_policy = template.lifecycle_policy

        result = service.migrate(
            source_policy,

            plan,
        )

        assert result.migrated_policy is not source_policy
        assert source_policy.allowed_states == (_STATE.REGISTERED, _STATE.ACTIVE)

        with pytest.raises(dataclasses.FrozenInstanceError):
            source_policy.initial_state = _STATE.ACTIVE


class TestRejectInvalidInputs:
    """None inputs and malformed migration steps are rejected."""

    def test_reject_none_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError
        ):
            service.plan(
                None,

                "1.0.0",

                "1.1.0",
            )

    def test_reject_blank_source_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService()
        template = _build_template()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError
        ):
            service.plan(
                template,

                "   ",

                "1.1.0",
            )

    def test_reject_none_lifecycle_policy(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService(
            steps={
                ("1.0.0", "1.1.0"): _add_suspended,
            },
        )
        template = _build_template()
        plan = service.plan(
            template,

            "1.0.0",

            "1.1.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError
        ):
            service.migrate(
                None,

                plan,
            )

    def test_reject_none_migration_plan(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService()
        template = _build_template()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError
        ):
            service.migrate(
                template.lifecycle_policy,

                None,
            )

    def test_reject_invalid_migration_step(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateMigrationService(
                steps={
                    ("1.0.0", "1.1.0"): "not-callable",
                },
            )
