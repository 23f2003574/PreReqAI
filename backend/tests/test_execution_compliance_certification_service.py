from types import (
    SimpleNamespace,
)

import pytest

from backend.session import (
    ExecutionComplianceCertification,
    ExecutionComplianceCertificationError as Error,
    ExecutionComplianceCertificationService,
)


class _FakeComplianceService:
    def __init__(self, rules, violations_by_change=None):
        self._rules = rules
        self._violations_by_change = violations_by_change or {}

    def rules(self):
        return self._rules

    def evaluate(self, change_id):
        return self._violations_by_change.get(change_id, ())


class _FakeExceptionService:
    def __init__(self, active_by_change=None):
        self._active_by_change = active_by_change or {}

    def active(self, change_id):
        return self._active_by_change.get(change_id, ())


class _FakeAttestationService:
    def __init__(self, attestations_by_change_rule=None):
        self._attestations_by_change_rule = attestations_by_change_rule or {}

    def for_rule(self, change_id, rule_id):
        return self._attestations_by_change_rule.get((change_id, rule_id), ())


def _rule(rule_id, severity):
    return SimpleNamespace(rule_id=rule_id, severity=severity)


def _violation(rule_id, severity):
    return {"rule_id": rule_id, "name": rule_id, "severity": severity}


def _exception(rule_id):
    return SimpleNamespace(rule_id=rule_id)


def _attestation(attestation_id, decision):
    return SimpleNamespace(attestation_id=attestation_id, decision=decision)


def _build(rules, violations_by_change=None, active_by_change=None, attestations_by_change_rule=None):
    compliance_service = _FakeComplianceService(rules, violations_by_change)
    exception_service = _FakeExceptionService(active_by_change)
    attestation_service = _FakeAttestationService(attestations_by_change_rule)
    return ExecutionComplianceCertificationService(compliance_service, exception_service, attestation_service)


class TestExecutionComplianceCertificationService:
    def test_successful_certification(self):
        service = _build(
            rules=[_rule("rule-1", "BLOCKING")],
            attestations_by_change_rule={("change-1", "rule-1"): (_attestation("attestation-1", "ACCEPT"),)},
        )

        certification = service.certify("change-1")

        assert isinstance(certification, ExecutionComplianceCertification)
        assert certification.status == "CERTIFIED"
        assert certification.rules_checked == ("rule-1",)
        assert certification.attestations == ("attestation-1",)

    def test_blocking_violation_fails_certification(self):
        service = _build(
            rules=[_rule("rule-1", "BLOCKING")],
            violations_by_change={"change-1": (_violation("rule-1", "BLOCKING"),)},
            attestations_by_change_rule={("change-1", "rule-1"): (_attestation("attestation-1", "ACCEPT"),)},
        )

        certification = service.certify("change-1")

        assert certification.status == "FAILED"

    def test_missing_attestation_fails_certification(self):
        service = _build(rules=[_rule("rule-1", "BLOCKING")])

        certification = service.certify("change-1")

        assert certification.status == "FAILED"
        assert certification.attestations == ()

    def test_exception_backed_certification(self):
        service = _build(
            rules=[_rule("rule-1", "BLOCKING")],
            violations_by_change={"change-1": (_violation("rule-1", "BLOCKING"),)},
            active_by_change={"change-1": (_exception("rule-1"),)},
            attestations_by_change_rule={("change-1", "rule-1"): (_attestation("attestation-1", "ACCEPT"),)},
        )

        certification = service.certify("change-1")

        assert certification.status == "CERTIFIED"

    def test_revocation(self):
        service = _build(
            rules=[_rule("rule-1", "BLOCKING")],
            attestations_by_change_rule={("change-1", "rule-1"): (_attestation("attestation-1", "ACCEPT"),)},
        )
        certification = service.certify("change-1")

        revoked = service.revoke(certification.certification_id, "control regressed")

        assert revoked.status == "REVOKED"
        assert revoked.reason == "control regressed"
        assert service.status("change-1") == "REVOKED"

    def test_revoking_a_failed_certification_is_an_error(self):
        service = _build(rules=[_rule("rule-1", "BLOCKING")])
        certification = service.certify("change-1")

        with pytest.raises(Error):
            service.revoke(certification.certification_id, "irrelevant")

    def test_certification_history(self):
        service = _build(
            rules=[_rule("rule-1", "BLOCKING")],
            attestations_by_change_rule={("change-1", "rule-1"): (_attestation("attestation-1", "ACCEPT"),)},
        )
        first = service.certify("change-1")
        second = service.certify("change-1")

        assert service.history("change-1") == (first, second)

    def test_status_never_certified_is_an_error(self):
        service = _build(rules=[])

        with pytest.raises(Error):
            service.status("unknown-change")
