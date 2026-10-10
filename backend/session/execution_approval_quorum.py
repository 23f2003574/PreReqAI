from dataclasses import (
    dataclass,
)

from .execution_approval_quorum_error import (
    ExecutionApprovalQuorumError,
)

STATUS_PENDING = "PENDING"

STATUS_SATISFIED = "SATISFIED"

STATUSES = (
    STATUS_PENDING,
    STATUS_SATISFIED,
)


@dataclass(frozen=True)
class ExecutionApprovalQuorum:
    """
    Immutable record of the independent approvals collected so far
    for an approval request that requires more than one approver
    before it may proceed.

    The quorum is a value object only. It performs no approval
    recording of its own; adding approvers and recomputing status is
    the responsibility of an execution approval quorum service, which
    produces a new record for every approval rather than mutating an
    existing one.

    Attributes:
        quorum_id: The quorum's unique identifier
        request_id: The identifier of the approval request this
            quorum gates
        required_count: How many unique approvers are required before
            the quorum is satisfied. Must be at least 1
        approvers: The unique approvers who have approved so far, in
            the order they approved
        status: The quorum's current state, one of STATUSES; SATISFIED
            exactly when len(approvers) >= required_count
    """

    quorum_id: str

    request_id: str

    required_count: int

    approvers: tuple

    status: str = STATUS_PENDING

    def __post_init__(self):
        self._require_text(self.quorum_id, "quorum ID")
        self._require_text(self.request_id, "request ID")

        if not isinstance(self.required_count, int) or isinstance(self.required_count, bool):
            raise ExecutionApprovalQuorumError(
                "Cannot build an execution approval quorum with a non-int required_count."
            )

        if self.required_count < 1:
            raise ExecutionApprovalQuorumError(
                "Cannot build an execution approval quorum with a required_count below 1."
            )

        if self.approvers is None:
            raise ExecutionApprovalQuorumError(
                "Cannot build an execution approval quorum with a None approvers collection."
            )

        approvers_list = list(self.approvers)

        for approver in approvers_list:
            if not isinstance(approver, str) or not approver.strip():
                raise ExecutionApprovalQuorumError(
                    "Cannot build an execution approval quorum with a blank approver."
                )

        if len(set(approvers_list)) != len(approvers_list):
            raise ExecutionApprovalQuorumError(
                "Cannot build an execution approval quorum with duplicate approvers."
            )

        object.__setattr__(self, "approvers", tuple(approvers_list))

        if self.status not in STATUSES:
            raise ExecutionApprovalQuorumError(
                f"Cannot build an execution approval quorum with an unknown status: {self.status!r}."
            )

        is_satisfied = len(self.approvers) >= self.required_count

        if is_satisfied and self.status != STATUS_SATISFIED:
            raise ExecutionApprovalQuorumError(
                "Cannot build an execution approval quorum: approvers meet required_count but status is not SATISFIED."
            )

        if not is_satisfied and self.status != STATUS_PENDING:
            raise ExecutionApprovalQuorumError(
                "Cannot build an execution approval quorum: status is SATISFIED but approvers do not meet required_count."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionApprovalQuorumError(
                f"Cannot build an execution approval quorum with an empty or blank {field_name}."
            )
