from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_compliance_certification_error import (
    ExecutionComplianceCertificationError,
)

STATUS_CERTIFIED = "CERTIFIED"

STATUS_FAILED = "FAILED"

STATUS_REVOKED = "REVOKED"

STATUSES = (
    STATUS_CERTIFIED,
    STATUS_FAILED,
    STATUS_REVOKED,
)


@dataclass(frozen=True)
class ExecutionComplianceCertification:
    """
    Immutable record of whether a change request satisfied every
    required compliance control at a point in time.

    The certification is a value object only. It performs no rule
    evaluation, exception lookup, or attestation checking of its own;
    weighing those into a certification, and revoking one, is the
    responsibility of an execution compliance certification service.
    A certification's own fields can never change once recorded:
    revoking a certified record produces a new, superseding record
    rather than editing the original in place.

    Attributes:
        certification_id: The certification's unique identifier
        change_id: The identifier of the change request this
            certification concerns
        status: The certification's outcome, one of STATUSES
        rules_checked: The identifiers of every rule considered
            during certification, in a fixed, sorted order
        attestations: The identifiers of every attestation relied
            upon, in a fixed, sorted order
        certified_at: When this certification was produced
        reason: Why a certified record was revoked, or None if it
            was not
    """

    certification_id: str

    change_id: str

    status: str

    rules_checked: tuple

    attestations: tuple

    certified_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    reason: str | None = None

    def __post_init__(self):
        self._require_text(self.certification_id, "certification ID")
        self._require_text(self.change_id, "change ID")

        if self.status not in STATUSES:
            raise ExecutionComplianceCertificationError(
                f"Cannot build an execution compliance certification with an unknown status: {self.status!r}."
            )

        object.__setattr__(self, "rules_checked", self._normalized(self.rules_checked, "rule ID"))
        object.__setattr__(self, "attestations", self._normalized(self.attestations, "attestation ID"))

        if not isinstance(self.certified_at, datetime):
            raise ExecutionComplianceCertificationError(
                "Cannot build an execution compliance certification with a non-datetime certified_at."
            )

        if self.status == STATUS_REVOKED:
            self._require_text(self.reason, "reason")
        elif self.reason is not None:
            raise ExecutionComplianceCertificationError(
                "Cannot build an execution compliance certification: only a revoked record can have a reason."
            )

    def _normalized(self, values, field_name: str) -> tuple:
        if values is None:
            raise ExecutionComplianceCertificationError(
                f"Cannot build an execution compliance certification with a None {field_name} collection."
            )

        values_list = list(values)

        for value in values_list:
            if not isinstance(value, str) or not value.strip():
                raise ExecutionComplianceCertificationError(
                    f"Cannot build an execution compliance certification with a blank {field_name}."
                )

        return tuple(values_list)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionComplianceCertificationError(
                f"Cannot build an execution compliance certification with an empty or blank {field_name}."
            )
