from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_compliance_attestation_error import (
    ExecutionComplianceAttestationError,
)

DECISION_ACCEPT = "ACCEPT"

DECISION_REJECT = "REJECT"

DECISIONS = (
    DECISION_ACCEPT,
    DECISION_REJECT,
)


@dataclass(frozen=True)
class ExecutionComplianceAttestation:
    """
    Immutable record of an authorized reviewer's formal attestation
    that the evidence collected for a rule's evaluation of a change
    request has been reviewed.

    The attestation is a value object only. It performs no
    authorization or evidence checking of its own; confirming an
    authorized reviewer and existing evidence, and recording an
    attestation, is the responsibility of an execution compliance
    attestation service. Once recorded, an attestation is never
    edited: a reviewer who changes their mind records a new,
    separate attestation.

    Attributes:
        attestation_id: The attestation's unique identifier
        change_id: The identifier of the change request this
            attestation concerns
        rule_id: The identifier of the compliance rule this
            attestation concerns
        reviewer: The identifier of the reviewer who attested
        decision: The reviewer's decision, one of DECISIONS
        reason: The reviewer's reasoning for their decision. Required
            for both an ACCEPT and a REJECT
        created_at: When this attestation was recorded
    """

    attestation_id: str

    change_id: str

    rule_id: str

    reviewer: str

    decision: str

    reason: str

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.attestation_id, "attestation ID")
        self._require_text(self.change_id, "change ID")
        self._require_text(self.rule_id, "rule ID")
        self._require_text(self.reviewer, "reviewer")
        self._require_text(self.reason, "reason")

        if self.decision not in DECISIONS:
            raise ExecutionComplianceAttestationError(
                f"Cannot build an execution compliance attestation with an unknown decision: {self.decision!r}."
            )

        if not isinstance(self.created_at, datetime):
            raise ExecutionComplianceAttestationError(
                "Cannot build an execution compliance attestation with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionComplianceAttestationError(
                f"Cannot build an execution compliance attestation with an empty or blank {field_name}."
            )
