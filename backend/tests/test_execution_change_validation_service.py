from types import (
    SimpleNamespace,
)

import pytest

from backend.session import (
    ExecutionChangeValidation,
    ExecutionChangeValidationError as Error,
    ExecutionChangeValidationService,
)


class _FakeChangeRequestService:
    def __init__(self, changes_by_id):
        self._changes_by_id = changes_by_id

    def find(self, change_id):
        changes = self._changes_by_id.get(change_id)

        if changes is None:
            return None

        return SimpleNamespace(change_id=change_id, changes=changes)

    def set_changes(self, change_id, changes):
        self._changes_by_id[change_id] = changes


def _build(changes_by_id=None):
    request_service = _FakeChangeRequestService(changes_by_id or {})
    return request_service, ExecutionChangeValidationService(request_service)


class TestExecutionChangeValidationService:
    def test_valid_change(self):
        _, service = _build({"change-1": {"max_concurrency": "4"}})

        result = service.validate("change-1")

        assert isinstance(result, ExecutionChangeValidation)
        assert result.valid is True
        assert result.violations == ()

    def test_invalid_change(self):
        _, service = _build({"change-1": {"safety_lock": "disabled"}})

        result = service.validate("change-1")

        assert result.valid is False
        assert result.violations == ("protected_key_changed:safety_lock",)

    def test_multiple_violations(self):
        _, service = _build(
            {"change-1": {"safety_lock": "disabled", "audit_logging": "off"}}
        )

        result = service.validate("change-1")

        assert result.valid is False
        assert set(result.violations) == {
            "protected_key_changed:safety_lock",
            "protected_key_changed:audit_logging",
        }

    def test_approval_blocked(self):
        _, service = _build({"change-1": {"safety_lock": "disabled"}})
        service.validate("change-1")

        assert service.can_approve("change-1") is False

    def test_revalidation(self):
        requests, service = _build({"change-1": {"safety_lock": "disabled"}})
        service.validate("change-1")
        assert service.can_approve("change-1") is False

        requests.set_changes("change-1", {"max_concurrency": "4"})
        result = service.revalidate("change-1")

        assert result.valid is True
        assert service.can_approve("change-1") is True

    def test_unknown_change_is_an_error(self):
        _, service = _build()

        with pytest.raises(Error):
            service.validate("unknown-change")
