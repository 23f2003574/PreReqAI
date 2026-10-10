from threading import (
    RLock,
)

from uuid import uuid4

from .execution_compliance_evidence import (
    ExecutionComplianceEvidence,
)

from .execution_compliance_evidence_error import (
    ExecutionComplianceEvidenceError,
)


class ExecutionComplianceEvidenceService:
    """
    Records verifiable evidence collected for a compliance rule's
    evaluation of a change request, so a reviewer can inspect why the
    change passed or failed.

    It operates over a change request service and a compliance
    service supplied at construction time, only to confirm that a
    change request and a rule exist before evidence is recorded
    against them; it never creates, evaluates, or modifies either.

    Behavior:
    - record() always requires the referenced change request and
      rule to already exist; evidence can never be recorded against
      an unknown change or rule
    - Evidence, once recorded, is never edited, replaced, or removed;
      every record method only reads what has already been recorded
    - collected_at is preserved exactly as recorded, never
      recalculated
    - verify() is read-only: it never mutates a record or the
      service's state, it only confirms and returns it

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, change_request_service, compliance_service):
        """
        Args:
            change_request_service: The service used to confirm a
                change request exists. Any object exposing
                `find(change_id)`, returning None if unknown, is
                accepted
            compliance_service: The service used to confirm a rule
                exists. Any object exposing `find(rule_id)`, returning
                None if unknown, is accepted
        """

        if change_request_service is None:
            raise ExecutionComplianceEvidenceError(
                "Cannot initialize execution compliance evidence service with a None change request service."
            )

        if compliance_service is None:
            raise ExecutionComplianceEvidenceError(
                "Cannot initialize execution compliance evidence service with a None compliance service."
            )

        self._change_request_service = change_request_service
        self._compliance_service = compliance_service
        self._evidence_by_id = {}
        self._evidence_ids_by_change = {}
        self._lock = RLock()

    def record(
        self,
        change_id: str,
        rule_id: str,
        source: str,
        value: str,
    ) -> ExecutionComplianceEvidence:
        """
        Record a new piece of evidence for a rule's evaluation of a
        change request.

        Raises:
            ExecutionComplianceEvidenceError: If change_id, rule_id,
                source, or value is None or blank, or no change
                request or rule is registered under change_id or
                rule_id
        """

        self._validate_text(change_id, "change ID")
        self._validate_text(rule_id, "rule ID")

        with self._lock:
            if self._change_request_service.find(change_id) is None:
                raise ExecutionComplianceEvidenceError(
                    f"Cannot record evidence: no change request is registered under change ID {change_id!r}."
                )

            if self._compliance_service.find(rule_id) is None:
                raise ExecutionComplianceEvidenceError(
                    f"Cannot record evidence: no rule is registered under rule ID {rule_id!r}."
                )

            evidence = ExecutionComplianceEvidence(
                evidence_id=str(uuid4()),
                change_id=change_id,
                rule_id=rule_id,
                source=source,
                value=value,
            )

            self._evidence_by_id[evidence.evidence_id] = evidence
            self._evidence_ids_by_change.setdefault(change_id, []).append(evidence.evidence_id)

            return evidence

    def evidence(self, change_id: str) -> tuple:
        """
        List every piece of evidence recorded for a change request,
        in the order it was recorded.

        Raises:
            ExecutionComplianceEvidenceError: If change_id is None or
                blank
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            return tuple(
                self._evidence_by_id[evidence_id]
                for evidence_id in self._evidence_ids_by_change.get(change_id, [])
            )

    def for_rule(self, change_id: str, rule_id: str) -> tuple:
        """
        List the evidence recorded for a specific rule's evaluation
        of a change request, in the order it was recorded.

        Raises:
            ExecutionComplianceEvidenceError: If change_id or rule_id
                is None or blank
        """

        self._validate_text(rule_id, "rule ID")

        return tuple(item for item in self.evidence(change_id) if item.rule_id == rule_id)

    def verify(self, evidence_id: str) -> ExecutionComplianceEvidence:
        """
        Confirm and return a recorded piece of evidence, exactly as
        it was recorded. Never mutates the record or the service's
        state.

        Raises:
            ExecutionComplianceEvidenceError: If evidence_id is None
                or blank, or no evidence is recorded under it
        """

        self._validate_text(evidence_id, "evidence ID")

        with self._lock:
            evidence = self._evidence_by_id.get(evidence_id)

            if evidence is None:
                raise ExecutionComplianceEvidenceError(
                    f"No evidence is recorded under evidence ID {evidence_id!r}."
                )

            return evidence

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionComplianceEvidenceError(f"Cannot use an empty or blank {field_name}.")
