import pytest

from backend.session import (
    ExecutionRecoveryConflict,
    ExecutionRecoveryConflictPolicy,
    ExecutionRecoveryConflictPolicyError as Error,
    ExecutionRecoveryConflictPolicyService,
)


def _service(conflicts):
    conflicts_by_id = {conflict.conflict_id: conflict for conflict in conflicts}
    recorded = {}

    def record_resolution(conflict_id, resolution):
        recorded[conflict_id] = resolution
        return conflicts_by_id[conflict_id]

    service = ExecutionRecoveryConflictPolicyService(
        conflict_resolver=conflicts_by_id.get,
        record_resolution=record_resolution,
    )

    return service, recorded


class TestExecutionRecoveryConflictPolicyService:
    def test_register_policy(self):
        policy = ExecutionRecoveryConflictPolicy(field="step", resolution="CHECKPOINT")
        service, _ = _service([])

        registered = service.register(policy)

        assert registered == policy
        assert service.policies("step") == (policy,)
        assert service.policies("other-field") == ()

        with pytest.raises(Error):
            service.register(policy)

    def test_automatic_resolution(self):
        conflict = ExecutionRecoveryConflict(
            session_id="session-1", checkpoint_id="checkpoint-1", field="step", checkpoint_value=5, current_value=3
        )
        service, recorded = _service([conflict])
        service.register(ExecutionRecoveryConflictPolicy(field="step", resolution="CHECKPOINT"))

        result = service.resolve(conflict.conflict_id)

        assert result == conflict
        assert recorded[conflict.conflict_id] == "CHECKPOINT"

        reject_conflict = ExecutionRecoveryConflict(
            session_id="session-1", checkpoint_id="checkpoint-1", field="danger", checkpoint_value=1, current_value=2
        )
        reject_service, reject_recorded = _service([reject_conflict])
        reject_service.register(ExecutionRecoveryConflictPolicy(field="danger", resolution="REJECT"))

        with pytest.raises(Error):
            reject_service.resolve(reject_conflict.conflict_id)

        assert reject_conflict.conflict_id not in reject_recorded

    def test_unmatched_conflict(self):
        conflict = ExecutionRecoveryConflict(
            session_id="session-1", checkpoint_id="checkpoint-1", field="other", checkpoint_value=5, current_value=3
        )
        service, recorded = _service([conflict])

        result = service.resolve(conflict.conflict_id)

        assert result is None
        assert conflict.conflict_id not in recorded

        with pytest.raises(Error):
            service.resolve("unknown-conflict")

    def test_disabled_policy(self):
        conflict = ExecutionRecoveryConflict(
            session_id="session-1", checkpoint_id="checkpoint-1", field="step", checkpoint_value=5, current_value=3
        )
        service, recorded = _service([conflict])
        policy = service.register(ExecutionRecoveryConflictPolicy(field="step", resolution="CHECKPOINT"))

        service.disable(policy.policy_id)

        result = service.resolve(conflict.conflict_id)

        assert result is None
        assert conflict.conflict_id not in recorded
        assert service.policies("step")[0].enabled is False

        with pytest.raises(Error):
            service.disable("unknown-policy")

    def test_resolution_precedence(self):
        conflict = ExecutionRecoveryConflict(
            session_id="session-1", checkpoint_id="checkpoint-1", field="step", checkpoint_value=5, current_value=3
        )
        service, recorded = _service([conflict])
        first = service.register(ExecutionRecoveryConflictPolicy(field="step", resolution="CHECKPOINT"))
        second = service.register(ExecutionRecoveryConflictPolicy(field="step", resolution="CURRENT"))

        service.resolve(conflict.conflict_id)

        assert recorded[conflict.conflict_id] == "CURRENT"
        assert service.policies("step") == (first, second)

        service.disable(second.policy_id)
        recorded.clear()

        service.resolve(conflict.conflict_id)

        assert recorded[conflict.conflict_id] == "CHECKPOINT"

    def test_invalid_resolution(self):
        with pytest.raises(Error):
            ExecutionRecoveryConflictPolicy(field="step", resolution="FOO")
