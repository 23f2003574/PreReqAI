import pytest

from backend.session import (
    ExecutionComplianceAttestation,
    ExecutionComplianceAttestationError as Error,
    ExecutionComplianceAttestationService,
)


class _FakeEvidenceService:
    def __init__(self, evidence_by_change_rule):
        self._evidence_by_change_rule = evidence_by_change_rule

    def for_rule(self, change_id, rule_id):
        return self._evidence_by_change_rule.get((change_id, rule_id), ())


def _build(evidence_by_change_rule=None, authorized_reviewers=("reviewer-1",)):
    if evidence_by_change_rule is None:
        evidence_by_change_rule = {("change-1", "rule-1"): ("evidence-1",)}

    evidence_service = _FakeEvidenceService(evidence_by_change_rule)
    return ExecutionComplianceAttestationService(evidence_service, authorized_reviewers)


class TestExecutionComplianceAttestationService:
    def test_accept_attestation(self):
        service = _build()

        attestation = service.attest("change-1", "rule-1", "reviewer-1", "ACCEPT", "evidence looks sufficient")

        assert isinstance(attestation, ExecutionComplianceAttestation)
        assert attestation.decision == "ACCEPT"
        assert service.valid("change-1") is True

    def test_reject_attestation(self):
        service = _build()

        attestation = service.attest("change-1", "rule-1", "reviewer-1", "REJECT", "evidence is insufficient")

        assert attestation.decision == "REJECT"

    def test_missing_evidence_is_rejected(self):
        service = _build(evidence_by_change_rule={})

        with pytest.raises(Error):
            service.attest("change-1", "rule-1", "reviewer-1", "ACCEPT", "looks fine")

    def test_unauthorized_reviewer_is_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.attest("change-1", "rule-1", "intruder", "ACCEPT", "looks fine")

    def test_history_lookup(self):
        service = _build(
            evidence_by_change_rule={
                ("change-1", "rule-1"): ("evidence-1",),
                ("change-1", "rule-2"): ("evidence-2",),
            }
        )
        first = service.attest("change-1", "rule-1", "reviewer-1", "ACCEPT", "fine")
        second = service.attest("change-1", "rule-2", "reviewer-1", "ACCEPT", "fine")

        assert service.history("change-1") == (first, second)
        assert service.for_rule("change-1", "rule-2") == (second,)

    def test_compliance_blocking(self):
        service = _build()
        service.attest("change-1", "rule-1", "reviewer-1", "REJECT", "not sufficient")

        assert service.valid("change-1") is False
