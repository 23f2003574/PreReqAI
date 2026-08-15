from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_compliance_evidence_error import (
    ExecutionComplianceEvidenceError,
)


@dataclass(frozen=True)
class ExecutionComplianceEvidence:
    """
    Immutable record of a single piece of evidence collected for a
    compliance rule's evaluation of a change request, so a reviewer
    can inspect why the change passed or failed that rule.

    The evidence is a value object only. It performs no collection or
    verification of its own; recording new evidence and verifying an
    existing record is the responsibility of an execution compliance
    evidence service. Once recorded, evidence is never edited or
    replaced: a later observation is recorded as a new, separate
    piece of evidence, never a mutation of an old one.

    Attributes:
        evidence_id: The evidence's unique identifier
        change_id: The identifier of the change request this evidence
            was collected for
        rule_id: The identifier of the compliance rule this evidence
            concerns
        source: Where this evidence came from (for example, a system,
            check, or reviewer)
        value: What was observed
        collected_at: When this evidence was collected. Preserved
            exactly as recorded; never recalculated or overwritten
    """

    evidence_id: str

    change_id: str

    rule_id: str

    source: str

    value: str

    collected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.evidence_id, "evidence ID")
        self._require_text(self.change_id, "change ID")
        self._require_text(self.rule_id, "rule ID")
        self._require_text(self.source, "source")
        self._require_text(self.value, "value")

        if not isinstance(self.collected_at, datetime):
            raise ExecutionComplianceEvidenceError(
                "Cannot build execution compliance evidence with a non-datetime collected_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionComplianceEvidenceError(
                f"Cannot build execution compliance evidence with an empty or blank {field_name}."
            )
