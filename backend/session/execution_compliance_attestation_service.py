from threading import (
    RLock,
)

from uuid import uuid4

from .execution_compliance_attestation import (
    DECISION_REJECT,
    ExecutionComplianceAttestation,
)

from .execution_compliance_attestation_error import (
    ExecutionComplianceAttestationError,
)


class ExecutionComplianceAttestationService:
    """
    Lets an authorized reviewer formally attest that the evidence
    collected for a rule's evaluation of a change request has been
    reviewed.

    It operates over an evidence service supplied at construction
    time to confirm evidence exists before an attestation can be
    recorded; it never records, edits, or removes evidence itself.
    Which reviewers are authorized to attest is fixed at construction
    time.

    Behavior:
    - attest() only succeeds for a reviewer in the authorized set,
      and only once evidence exists for the given change and rule; an
      attestation can never be recorded for either an unauthorized
      reviewer or a rule with no evidence
    - Every attestation, ACCEPT or REJECT, is retained; a later
      attestation never replaces or removes an earlier one
    - valid() reflects whether a change request has ever received a
      REJECT attestation: a single REJECT blocks compliance, even if
      other attestations for the same change accepted

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, evidence_service, authorized_reviewers):
        """
        Args:
            evidence_service: The service used to confirm evidence
                exists for a change and rule. Any object exposing
                `for_rule(change_id, rule_id)`, returning an empty
                collection if none exists, is accepted
            authorized_reviewers: The identifiers of reviewers
                permitted to attest

        Raises:
            ExecutionComplianceAttestationError: If evidence_service
                or authorized_reviewers is None
        """

        if evidence_service is None:
            raise ExecutionComplianceAttestationError(
                "Cannot initialize execution compliance attestation service with a None evidence service."
            )

        if authorized_reviewers is None:
            raise ExecutionComplianceAttestationError(
                "Cannot initialize execution compliance attestation service with None authorized_reviewers."
            )

        self._evidence_service = evidence_service
        self._authorized_reviewers = frozenset(authorized_reviewers)
        self._attestation_ids_by_change = {}
        self._attestations_by_id = {}
        self._lock = RLock()

    def attest(
        self,
        change_id: str,
        rule_id: str,
        reviewer: str,
        decision: str,
        reason: str,
    ) -> ExecutionComplianceAttestation:
        """
        Record a new attestation.

        Raises:
            ExecutionComplianceAttestationError: If change_id,
                rule_id, reviewer, decision, or reason is None or
                blank, reviewer is not authorized, or no evidence has
                been recorded for change_id and rule_id
        """

        self._validate_text(change_id, "change ID")
        self._validate_text(rule_id, "rule ID")
        self._validate_text(reviewer, "reviewer")

        with self._lock:
            if reviewer not in self._authorized_reviewers:
                raise ExecutionComplianceAttestationError(
                    f"Cannot attest: reviewer {reviewer!r} is not an authorized reviewer."
                )

            if not self._evidence_service.for_rule(change_id, rule_id):
                raise ExecutionComplianceAttestationError(
                    f"Cannot attest to rule ID {rule_id!r} for change ID {change_id!r}: no evidence has been recorded."
                )

            attestation = ExecutionComplianceAttestation(
                attestation_id=str(uuid4()),
                change_id=change_id,
                rule_id=rule_id,
                reviewer=reviewer,
                decision=decision,
                reason=reason,
            )

            self._attestations_by_id[attestation.attestation_id] = attestation
            self._attestation_ids_by_change.setdefault(change_id, []).append(attestation.attestation_id)

            return attestation

    def history(self, change_id: str) -> tuple:
        """
        List every attestation recorded for a change request, in the
        order it was recorded.

        Raises:
            ExecutionComplianceAttestationError: If change_id is None
                or blank
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            return tuple(
                self._attestations_by_id[attestation_id]
                for attestation_id in self._attestation_ids_by_change.get(change_id, [])
            )

    def for_rule(self, change_id: str, rule_id: str) -> tuple:
        """
        List the attestations recorded for a specific rule against a
        change request, in the order they were recorded.

        Raises:
            ExecutionComplianceAttestationError: If change_id or
                rule_id is None or blank
        """

        self._validate_text(rule_id, "rule ID")

        return tuple(item for item in self.history(change_id) if item.rule_id == rule_id)

    def valid(self, change_id: str) -> bool:
        """
        Whether a change request's attestations satisfy compliance: a
        single REJECT attestation blocks compliance, regardless of
        any other attestation.

        Raises:
            ExecutionComplianceAttestationError: If change_id is None
                or blank
        """

        return not any(item.decision == DECISION_REJECT for item in self.history(change_id))

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionComplianceAttestationError(f"Cannot use an empty or blank {field_name}.")
