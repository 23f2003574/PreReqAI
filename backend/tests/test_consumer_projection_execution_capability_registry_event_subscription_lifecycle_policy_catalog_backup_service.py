import dataclasses

from datetime import datetime

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackup,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogRecoveryResult,
)


REGISTERED = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED
ACTIVE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            REGISTERED,
            ACTIVE,
        ),
        initial_state,
    )


def _build_metadata():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata(
        catalog_name="core-lifecycle-policies",

        catalog_version="1.0.0",

        description="Core lifecycle policy catalog.",
    )


def _build_catalog(policies):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
        _build_metadata(),

        policies,
    )


class TestCreateBackup:
    """A backup can be created from a policy catalog."""

    def test_create_backup(self):
        catalog = _build_catalog(
            {
                "registered-default": _build_policy(REGISTERED),
            }
        )

        backup = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService().create_backup(
            catalog,

            "backup-1",
        )

        assert isinstance(
            backup,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackup,
        )
        assert backup.backup_id == "backup-1"
        assert backup.catalog is catalog
        assert isinstance(backup.created_at, datetime)


class TestRecoverCatalog:
    """Recovering a backup returns the exact catalog it captured."""

    def test_recover_catalog(self):
        catalog = _build_catalog(
            {
                "registered-default": _build_policy(REGISTERED),
            }
        )

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService()

        backup = service.create_backup(
            catalog,

            "backup-1",
        )

        result = service.recover(backup)

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogRecoveryResult,
        )
        assert result.recovered_catalog is catalog
        assert result.backup_id == "backup-1"
        assert result.recovery_successful is True


class TestVerifyValidBackup:
    """A backup with intact metadata and policies verifies as valid."""

    def test_verify_valid_backup(self):
        catalog = _build_catalog(
            {
                "registered-default": _build_policy(REGISTERED),
            }
        )

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService()

        backup = service.create_backup(
            catalog,

            "backup-1",
        )

        assert service.verify_backup(backup) is True


class TestVerifyInvalidBackup:
    """A backup referencing a catalog with a None policy verifies as invalid."""

    def test_verify_invalid_backup(self):
        malformed_catalog = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog(
            metadata=_build_metadata(),

            policies={
                "broken": None,
            },
        )

        malformed_backup = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackup(
            backup_id="backup-broken",

            catalog=malformed_catalog,

            created_at=datetime.now(),
        )

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService()

        assert service.verify_backup(malformed_backup) is False


class TestPreserveCatalogOrdering:
    """Recovery preserves the exact ordering of the backed-up catalog."""

    def test_preserve_catalog_ordering(self):
        catalog = _build_catalog(
            [
                ("zeta", _build_policy(REGISTERED)),
                ("alpha", _build_policy(ACTIVE)),
            ]
        )

        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService()

        backup = service.create_backup(
            catalog,

            "backup-1",
        )

        result = service.recover(backup)

        assert list(result.recovered_catalog.policies.keys()) == [
            "zeta",
            "alpha",
        ]


class TestImmutableBackup:
    """A created backup cannot have its fields reassigned."""

    def test_immutable_backup(self):
        catalog = _build_catalog({})

        backup = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService().create_backup(
            catalog,

            "backup-1",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            backup.backup_id = "renamed"


class TestRejectDuplicateBackupIds:
    """A backup ID reused on the same service instance is rejected."""

    def test_reject_duplicate_backup_ids(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService()

        service.create_backup(
            _build_catalog({}),

            "backup-1",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError
        ):
            service.create_backup(
                _build_catalog({}),

                "backup-1",
            )


class TestRejectInvalidInputs:
    """None inputs, blank backup IDs, and invalid backups are rejected."""

    def test_reject_none_catalog_on_create(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService().create_backup(
                None,

                "backup-1",
            )

    def test_reject_none_backup_id_on_create(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService().create_backup(
                _build_catalog({}),

                None,
            )

    def test_reject_blank_backup_id_on_create(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService().create_backup(
                _build_catalog({}),

                "",
            )

    def test_reject_none_backup_on_recover(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService().recover(
                None
            )

    def test_reject_invalid_backup_on_recover(self):
        malformed_backup = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackup(
            backup_id="backup-broken",

            catalog=None,

            created_at=datetime.now(),
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService().recover(
                malformed_backup
            )

    def test_reject_none_backup_on_verify(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBackupService().verify_backup(
                None
            )
