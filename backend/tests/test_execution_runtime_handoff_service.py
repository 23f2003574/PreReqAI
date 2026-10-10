import pytest

from backend.session import (
    ExecutionRuntimeHandoff,
    ExecutionRuntimeHandoffError as Error,
    ExecutionRuntimeHandoffService,
)


class _FakeStateRecord:
    def __init__(self, state):
        self.state = state


class _FakeStateService:
    def __init__(self, state_by_runtime=None):
        self._state_by_runtime = dict(state_by_runtime or {})

    def state(self, runtime_id):
        if runtime_id not in self._state_by_runtime:
            raise ValueError(f"unknown runtime {runtime_id!r}")

        return _FakeStateRecord(self._state_by_runtime[runtime_id])


class _FakeCheckpointService:
    def __init__(self, valid_checkpoint_ids=None):
        if valid_checkpoint_ids is None:
            valid_checkpoint_ids = {"checkpoint-1"}

        self._valid_checkpoint_ids = set(valid_checkpoint_ids)

    def valid(self, checkpoint_id):
        return checkpoint_id in self._valid_checkpoint_ids


def _build(state_by_runtime=None, valid_checkpoint_ids=None):
    state_service = _FakeStateService(state_by_runtime or {"runtime-1": "FAILED"})
    checkpoint_service = _FakeCheckpointService(valid_checkpoint_ids)
    return state_service, checkpoint_service, ExecutionRuntimeHandoffService(
        state_service, checkpoint_service
    )


class TestExecutionRuntimeHandoffService:
    def test_create_handoff(self):
        _, _, service = _build()

        handoff = service.create("runtime-1", "checkpoint-1", "runtime crashed")

        assert isinstance(handoff, ExecutionRuntimeHandoff)
        assert handoff.runtime_id == "runtime-1"
        assert handoff.checkpoint_id == "checkpoint-1"
        assert handoff.status == "PENDING"

    def test_accept(self):
        _, _, service = _build()
        handoff = service.create("runtime-1", "checkpoint-1", "runtime crashed")

        accepted = service.accept(handoff.handoff_id)

        assert accepted.status == "ACCEPTED"
        assert service.status(handoff.handoff_id) == "ACCEPTED"

    def test_reject(self):
        _, _, service = _build()
        handoff = service.create("runtime-1", "checkpoint-1", "runtime crashed")

        rejected = service.reject(handoff.handoff_id, "checkpoint corrupted")

        assert rejected.status == "REJECTED"
        assert rejected.reason == "checkpoint corrupted"
        assert service.status(handoff.handoff_id) == "REJECTED"

    def test_invalid_runtime(self):
        _, _, service = _build(state_by_runtime={"runtime-1": "RUNNING"})

        with pytest.raises(Error):
            service.create("runtime-1", "checkpoint-1", "attempt handoff")

    def test_invalid_checkpoint(self):
        _, _, service = _build(valid_checkpoint_ids=set())

        with pytest.raises(Error):
            service.create("runtime-1", "checkpoint-1", "attempt handoff")

    def test_duplicate_acceptance(self):
        _, _, service = _build()
        handoff = service.create("runtime-1", "checkpoint-1", "runtime crashed")
        service.accept(handoff.handoff_id)

        with pytest.raises(Error):
            service.accept(handoff.handoff_id)

    def test_rejecting_accepted_handoff_is_rejected(self):
        _, _, service = _build()
        handoff = service.create("runtime-1", "checkpoint-1", "runtime crashed")
        service.accept(handoff.handoff_id)

        with pytest.raises(Error):
            service.reject(handoff.handoff_id, "too late")

    def test_accepting_rejected_handoff_is_rejected(self):
        _, _, service = _build()
        handoff = service.create("runtime-1", "checkpoint-1", "runtime crashed")
        service.reject(handoff.handoff_id, "checkpoint corrupted")

        with pytest.raises(Error):
            service.accept(handoff.handoff_id)

    def test_status_lookup_for_unknown_handoff_is_rejected(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.status("does-not-exist")

    def test_creating_handoff_for_unknown_runtime_is_rejected(self):
        _, _, service = _build()

        with pytest.raises(Error):
            service.create("does-not-exist", "checkpoint-1", "reason")
