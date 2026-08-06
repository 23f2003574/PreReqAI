import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceRule as Rule,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceService as ComplianceService,
)


def _rule(rule_id="rule-1", severity="CRITICAL", enabled=True):
    return Rule(rule_id=rule_id, name="no untagged resources", severity=severity, enabled=enabled)


def _checker_flagging(*rule_ids):
    def _checker(rule, session_id):
        return rule.rule_id in rule_ids

    return _checker


class TestWorkspaceSessionComplianceService:
    def test_compliant_session(self):
        service = ComplianceService(rules=[_rule()])

        result = service.evaluate("session-1")

        assert isinstance(result, Result)
        assert result.compliant is True
        assert result.violations == ()

    def test_critical_violation(self):
        service = ComplianceService(
            rules=[_rule(rule_id="rule-1", severity="CRITICAL")],
            violation_checker=_checker_flagging("rule-1"),
        )

        with pytest.raises(Error):
            service.evaluate("session-1")

        # the blocking evaluation is still retained for later reporting
        result = service.report("session-1")
        assert result.compliant is False
        assert result.violations == ("rule-1",)

    def test_enable_disable_rule(self):
        service = ComplianceService(rules=[_rule(rule_id="rule-1")])

        service.disable("rule-1")
        assert service.active_rules() == ()

        service.enable("rule-1")
        assert [rule.rule_id for rule in service.active_rules()] == ["rule-1"]

        with pytest.raises(Error):
            service.enable("unknown-rule")

        with pytest.raises(Error):
            service.disable("unknown-rule")

    def test_active_rule_lookup(self):
        service = ComplianceService(
            rules=[
                _rule(rule_id="rule-1", enabled=True),
                _rule(rule_id="rule-2", enabled=False),
            ]
        )

        active_ids = {rule.rule_id for rule in service.active_rules()}
        assert active_ids == {"rule-1"}

    def test_compliance_report(self):
        service = ComplianceService(
            rules=[_rule(rule_id="rule-1", severity="WARNING")],
            violation_checker=_checker_flagging("rule-1"),
        )

        with pytest.raises(Error):
            service.report("session-1")

        evaluated = service.evaluate("session-1")
        reported = service.report("session-1")

        assert reported == evaluated
        assert reported.compliant is False
        assert reported.violations == ("rule-1",)

    def test_disabled_rule_ignored(self):
        service = ComplianceService(
            rules=[_rule(rule_id="rule-1", severity="CRITICAL", enabled=False)],
            violation_checker=_checker_flagging("rule-1"),
        )

        # a disabled rule is never evaluated, even though the checker would flag it
        result = service.evaluate("session-1")

        assert result.compliant is True
        assert result.violations == ()
