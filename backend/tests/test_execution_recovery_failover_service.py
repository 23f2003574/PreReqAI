import pytest

from backend.session import (
    ExecutionRecoveryFailoverError as Error,
    ExecutionRecoveryFailoverService,
)


def _service(valid_checkpoint_ids):
    return ExecutionRecoveryFailoverService(
        checkpoint_validation_resolver=lambda checkpoint_id: checkpoint_id in valid_checkpoint_ids,
    )


class TestExecutionRecoveryFailoverService:
    def test_successful_primary_recovery(self):
        failover_service = _service({"checkpoint-primary"})
        failover_service.register("session-1", ["checkpoint-primary", "checkpoint-backup-1"])

        resolved = failover_service.execute("session-1")

        assert resolved.status == "RESOLVED"
        assert resolved.selected_checkpoint == "checkpoint-primary"

        again = failover_service.execute("session-1")
        assert again == resolved

    def test_backup_selection(self):
        failover_service = _service({"checkpoint-backup-1"})
        failover_service.register("session-1", ["checkpoint-primary", "checkpoint-backup-1"])

        resolved = failover_service.execute("session-1")

        assert resolved.status == "RESOLVED"
        assert resolved.selected_checkpoint == "checkpoint-backup-1"

    def test_invalid_checkpoint_skip(self):
        failover_service = _service({"checkpoint-backup-2"})
        failover_service.register(
            "session-1", ["checkpoint-primary", "checkpoint-backup-1", "checkpoint-backup-2"]
        )

        resolved = failover_service.execute("session-1")

        assert resolved.status == "RESOLVED"
        assert resolved.selected_checkpoint == "checkpoint-backup-2"

    def test_all_checkpoints_invalid(self):
        failover_service = _service(set())
        failover_service.register("session-1", ["checkpoint-primary", "checkpoint-backup-1"])

        exhausted = failover_service.execute("session-1")

        assert exhausted.status == "EXHAUSTED"
        assert exhausted.selected_checkpoint is None

        with pytest.raises(Error):
            failover_service.execute("unknown-session")

    def test_selection_status_lookup(self):
        failover_service = _service({"checkpoint-primary"})
        failover_service.register("session-1", ["checkpoint-primary", "checkpoint-backup-1"])

        assert failover_service.status("session-1") == "PENDING"
        assert failover_service.select("session-1") is None

        failover_service.execute("session-1")

        assert failover_service.status("session-1") == "RESOLVED"
        assert failover_service.select("session-1") == "checkpoint-primary"

        with pytest.raises(Error):
            failover_service.status("unknown-session")

        with pytest.raises(Error):
            failover_service.select("unknown-session")
