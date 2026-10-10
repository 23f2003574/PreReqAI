from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from types import (
    MappingProxyType,
)

from typing import (
    Mapping,
)

from .execution_change_request_error import (
    ExecutionChangeRequestError,
)

STATUS_PENDING = "PENDING"

STATUS_APPROVED = "APPROVED"

STATUS_REJECTED = "REJECTED"

STATUS_APPLIED = "APPLIED"

STATUSES = (
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_APPLIED,
)


@dataclass(frozen=True)
class ExecutionChangeRequest:
    """
    Immutable record of a request to modify a session's governed
    execution configuration.

    The request is a value object only. It performs no state
    transition of its own and never modifies configuration itself;
    creating, approving, rejecting, and applying requests is the
    responsibility of an execution change request service, which
    produces a new record for every transition rather than mutating
    an existing one.

    Attributes:
        change_id: The request's unique identifier
        session_id: The identifier of the execution session whose
            configuration the request would modify
        requested_by: The identifier of who requested the change
        changes: The configuration keys to change, mapped to their
            new value, or None to delete that key. Never empty
        status: The request's current state, one of STATUSES
        created_at: When the request was created
        approver: The identifier of who approved or rejected the
            request, or None while it is still pending
        reason: Why the request was rejected, or None otherwise
        decided_at: When the request was approved or rejected, or
            None while it is still pending
        applied_at: When the request's changes were applied, or None
            if they have not been
    """

    change_id: str

    session_id: str

    requested_by: str

    changes: Mapping

    status: str = STATUS_PENDING

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    approver: str | None = None

    reason: str | None = None

    decided_at: datetime | None = None

    applied_at: datetime | None = None

    def __post_init__(self):
        self._require_text(self.change_id, "change ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.requested_by, "requested_by")

        if self.changes is None or not self.changes:
            raise ExecutionChangeRequestError(
                "Cannot build an execution change request with an empty or None changes mapping."
            )

        for key, value in self.changes.items():
            if not isinstance(key, str) or not key.strip():
                raise ExecutionChangeRequestError(
                    "Cannot build an execution change request with a blank change key."
                )

            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ExecutionChangeRequestError(
                    f"Cannot build an execution change request with an invalid value for change key {key!r}."
                )

        object.__setattr__(self, "changes", MappingProxyType(dict(self.changes)))

        if self.status not in STATUSES:
            raise ExecutionChangeRequestError(
                f"Cannot build an execution change request with an unknown status: {self.status!r}."
            )

        if not isinstance(self.created_at, datetime):
            raise ExecutionChangeRequestError(
                "Cannot build an execution change request with a non-datetime created_at."
            )

        is_pending = self.status == STATUS_PENDING

        if is_pending and (self.approver is not None or self.decided_at is not None):
            raise ExecutionChangeRequestError(
                "Cannot build an execution change request: a pending request cannot have an approver or decided_at."
            )

        if not is_pending:
            self._require_text(self.approver, "approver")

            if self.decided_at is None:
                raise ExecutionChangeRequestError(
                    "Cannot build an execution change request: an approved, rejected, or applied request must have a decided_at."
                )

        if self.status == STATUS_REJECTED:
            self._require_text(self.reason, "reason")
        elif self.reason is not None:
            raise ExecutionChangeRequestError(
                "Cannot build an execution change request: only a rejected request can have a reason."
            )

        if self.status == STATUS_APPLIED:
            if self.applied_at is None:
                raise ExecutionChangeRequestError(
                    "Cannot build an execution change request: an applied request must have an applied_at."
                )
        elif self.applied_at is not None:
            raise ExecutionChangeRequestError(
                "Cannot build an execution change request: only an applied request can have an applied_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionChangeRequestError(
                f"Cannot build an execution change request with an empty or blank {field_name}."
            )
