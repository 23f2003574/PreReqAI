import dataclasses

from types import (
    SimpleNamespace,
)

import pytest

from backend.session import (
    ExecutionComplianceEvidence,
    ExecutionComplianceEvidenceError as Error,
    ExecutionComplianceEvidenceService,
)


class _FakeRegistry:
    def __init__(self, known_ids):
        self._known_ids = set(known_ids)

    def find(self, entity_id):
        if entity_id not in self._known_ids:
            return None

        return SimpleNamespace(id=entity_id)


def _build(known_changes=("change-1",), known_rules=("rule-1",)):
    change_request_service = _FakeRegistry(known_changes)
    compliance_service = _FakeRegistry(known_rules)
    return ExecutionComplianceEvidenceService(change_request_service, compliance_service)


class TestExecutionComplianceEvidenceService:
    def test_record_evidence(self):
        service = _build()

        evidence = service.record("change-1", "rule-1", "ci-pipeline", "checks passed")

        assert isinstance(evidence, ExecutionComplianceEvidence)
        assert evidence.change_id == "change-1"
        assert evidence.rule_id == "rule-1"
        assert evidence.source == "ci-pipeline"
        assert evidence.value == "checks passed"

    def test_rule_filtering(self):
        service = _build(known_rules=("rule-1", "rule-2"))
        first = service.record("change-1", "rule-1", "ci-pipeline", "checks passed")
        service.record("change-1", "rule-2", "reviewer", "looks fine")

        result = service.for_rule("change-1", "rule-1")

        assert result == (first,)

    def test_change_filtering(self):
        service = _build(known_changes=("change-1", "change-2"))
        first = service.record("change-1", "rule-1", "ci-pipeline", "checks passed")
        service.record("change-2", "rule-1", "ci-pipeline", "checks passed")

        result = service.evidence("change-1")

        assert result == (first,)

    def test_evidence_is_immutable(self):
        service = _build()
        evidence = service.record("change-1", "rule-1", "ci-pipeline", "checks passed")

        with pytest.raises(dataclasses.FrozenInstanceError):
            evidence.value = "tampered"

    def test_verification(self):
        service = _build()
        evidence = service.record("change-1", "rule-1", "ci-pipeline", "checks passed")

        verified = service.verify(evidence.evidence_id)

        assert verified == evidence
        assert service.evidence("change-1") == (evidence,)

    def test_unknown_change_is_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.record("unknown-change", "rule-1", "ci-pipeline", "checks passed")

    def test_unknown_rule_is_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.record("change-1", "unknown-rule", "ci-pipeline", "checks passed")
