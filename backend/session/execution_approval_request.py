from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_approval_error import (
    ExecutionApprovalError,
)

STATUS_PENDING = "PENDING"

STATUS_APPROVED = "APPROVED"

STATUS_REJECTED = "REJECTED"

STATUSES = (
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_REJECTED,
)


@dataclass(frozen=True)
class ExecutionApprovalRequest:
    """
    Immutable record of a request for explicit approval before a
    governed execution action may proceed.

    The request is a value object only. It performs no state
    transition of its own; creating, approving, and rejecting
    requests is the responsibility of an execution approval service,
    which produces a new record for every transition rather than
    mutating an existing one.

    Attributes:
        request_id: The request's unique identifier
        session_id: The identifier of the execution session the
            requested action belongs to
        action: The governed action awaiting approval
        requester: The identifier of who requested the action
        status: The request's current state, one of STATUSES
        created_at: When the request was created
        approver: The identifier of who approved or rejected the
            request, or None while it is still pending
        reason: Why the request was rejected, or None if it is
            pending or approved
        decided_at: When the request was approved or rejected, or
            None while it is still pending
    """

    request_id: str

    session_id: str

    action: str

    requester: str

    status: str = STATUS_PENDING

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    approver: str | None = None

    reason: str | None = None

    decided_at: datetime | None = None

    def __post_init__(self):
        self._require_text(self.request_id, "request ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.action, "action")
        self._require_text(self.requester, "requester")

        if self.status not in STATUSES:
            raise ExecutionApprovalError(
                f"Cannot build an execution approval request with an unknown status: {self.status!r}."
            )

        if not isinstance(self.created_at, datetime):
            raise ExecutionApprovalError(
                "Cannot build an execution approval request with a non-datetime created_at."
            )

        is_pending = self.status == STATUS_PENDING

        if is_pending and (self.approver is not None or self.decided_at is not None):
            raise ExecutionApprovalError(
                "Cannot build an execution approval request: a pending request cannot have an approver or decided_at."
            )

        if not is_pending:
            self._require_text(self.approver, "approver")

            if self.decided_at is None:
                raise ExecutionApprovalError(
                    "Cannot build an execution approval request: an approved or rejected request must have a decided_at."
                )

        if self.status == STATUS_REJECTED:
            self._require_text(self.reason, "reason")

        if self.status != STATUS_REJECTED and self.reason is not None:
            raise ExecutionApprovalError(
                "Cannot build an execution approval request: only a rejected request can have a reason."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionApprovalError(
                f"Cannot build an execution approval request with an empty or blank {field_name}."
            )
