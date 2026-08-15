from types import (
    SimpleNamespace,
)

import pytest

from backend.session import (
    ExecutionComplianceError as Error,
    ExecutionComplianceRule,
    ExecutionComplianceService,
)


class _FakeChangeRequestService:
    def __init__(self, changes_by_id):
        self._changes_by_id = changes_by_id

    def find(self, change_id):
        changes = self._changes_by_id.get(change_id)

        if changes is None:
            return None

        return SimpleNamespace(change_id=change_id, changes=changes)


def _build(changes_by_id=None):
    request_service = _FakeChangeRequestService(changes_by_id or {})
    return ExecutionComplianceService(request_service)


def _rule(rule_id, condition, severity, enabled=True):
    return ExecutionComplianceRule(
        rule_id=rule_id,
        name=rule_id,
        condition=condition,
        severity=severity,
        enabled=enabled,
    )


class TestExecutionComplianceService:
    def test_register_and_evaluate(self):
        service = _build({"change-1": {"max_concurrency": "4"}})
        rule = _rule("has-reason", lambda changes: "reason" not in changes, "WARNING")

        registered = service.register(rule)

        assert registered == rule

        violations = service.evaluate("change-1")

        assert violations == ()

    def test_warning_violation(self):
        service = _build({"change-1": {"reason": "test"}})
        service.register(_rule("no-reason-key", lambda changes: "reason" not in changes, "WARNING"))

        violations = service.evaluate("change-1")

        assert len(violations) == 1
        assert violations[0]["severity"] == "WARNING"
        assert violations[0]["rule_id"] == "no-reason-key"

    def test_blocking_violation(self):
        service = _build({"change-1": {"safety_lock": "off"}})
        service.register(_rule("no-safety-lock", lambda changes: "safety_lock" not in changes, "BLOCKING"))

        violations = service.evaluate("change-1")

        assert len(violations) == 1
        assert violations[0]["severity"] == "BLOCKING"

    def test_disabled_rule_is_ignored(self):
        service = _build({"change-1": {"safety_lock": "off"}})
        rule = service.register(
            _rule("no-safety-lock", lambda changes: "safety_lock" not in changes, "BLOCKING")
        )

        service.disable(rule.rule_id)
        violations = service.evaluate("change-1")

        assert violations == ()

    def test_multiple_violations(self):
        service = _build({"change-1": {"safety_lock": "off", "reason": None}})
        service.register(_rule("no-safety-lock", lambda changes: "safety_lock" not in changes, "BLOCKING"))
        service.register(_rule("has-reason", lambda changes: changes.get("reason") is not None, "WARNING"))

        violations = service.evaluate("change-1")

        assert len(violations) == 2
        assert {violation["rule_id"] for violation in violations} == {"no-safety-lock", "has-reason"}

    def test_approval_blocked(self):
        service = _build({"change-1": {"safety_lock": "off"}})
        service.register(_rule("no-safety-lock", lambda changes: "safety_lock" not in changes, "BLOCKING"))
        service.register(_rule("has-reason", lambda changes: "reason" in changes, "WARNING"))

        service.evaluate("change-1")

        assert service.can_approve("change-1") is False

    def test_only_warnings_do_not_block_approval(self):
        service = _build({"change-1": {}})
        service.register(_rule("has-reason", lambda changes: "reason" in changes, "WARNING"))

        service.evaluate("change-1")

        assert service.can_approve("change-1") is True
