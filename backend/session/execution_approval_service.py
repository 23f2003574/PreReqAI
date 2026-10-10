from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_approval_error import (
    ExecutionApprovalError,
)

from .execution_approval_request import (
    ExecutionApprovalRequest,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
)


class ExecutionApprovalService:
    """
    Requires explicit approval before a governed execution action may
    proceed, by tracking approval requests through a pending,
    approved, or rejected lifecycle.

    Behavior:
    - create() always starts a new request as PENDING
    - Only a PENDING request can be approved or rejected; once
      decided, a request is terminal and can never change state
      again, including being decided a second time
    - approve() records the approver; reject() requires a non-blank
      reason and records both the approver and the reason
    - pending() lists only the requests still awaiting a decision for
      a session

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._requests_by_id = {}
        self._request_ids_by_session = {}
        self._lock = RLock()

    def create(
        self,
        session_id: str,
        action: str,
        requester: str,
    ) -> ExecutionApprovalRequest:
        """
        Create a new, pending approval request.

        Raises:
            ExecutionApprovalError: If session_id, action, or
                requester is None or blank
        """

        with self._lock:
            request = ExecutionApprovalRequest(
                request_id=str(uuid4()),
                session_id=session_id,
                action=action,
                requester=requester,
                status=STATUS_PENDING,
            )

            self._requests_by_id[request.request_id] = request
            self._request_ids_by_session.setdefault(session_id, []).append(request.request_id)

            return request

    def approve(self, request_id: str, approver: str) -> ExecutionApprovalRequest:
        """
        Approve a pending request.

        Raises:
            ExecutionApprovalError: If request_id or approver is None
                or blank, no request is registered under request_id,
                or the request is not pending
        """

        self._validate_text(approver, "approver")

        return self._decide(request_id, STATUS_APPROVED, approver, reason=None)

    def reject(self, request_id: str, approver: str, reason: str) -> ExecutionApprovalRequest:
        """
        Reject a pending request.

        Raises:
            ExecutionApprovalError: If request_id, approver, or reason
                is None or blank, no request is registered under
                request_id, or the request is not pending
        """

        self._validate_text(approver, "approver")
        self._validate_text(reason, "reason")

        return self._decide(request_id, STATUS_REJECTED, approver, reason=reason)

    def pending(self, scope_id: str) -> list:
        """
        List the requests still awaiting a decision for a session.

        Raises:
            ExecutionApprovalError: If scope_id is None or blank
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            return [
                self._requests_by_id[request_id]
                for request_id in self._request_ids_by_session.get(scope_id, [])
                if self._requests_by_id[request_id].status == STATUS_PENDING
            ]

    def status(self, request_id: str) -> str:
        """
        Look up a request's current status.

        Raises:
            ExecutionApprovalError: If request_id is None or blank, or
                no request is registered under it
        """

        self._validate_text(request_id, "request ID")

        with self._lock:
            return self._resolve(request_id).status

    def _decide(
        self,
        request_id: str,
        outcome: str,
        approver: str,
        reason: str | None,
    ) -> ExecutionApprovalRequest:
        self._validate_text(request_id, "request ID")

        with self._lock:
            request = self._resolve(request_id)

            if request.status != STATUS_PENDING:
                verb = "approve" if outcome == STATUS_APPROVED else "reject"

                raise ExecutionApprovalError(
                    f"Cannot {verb} request ID {request_id!r}: it is {request.status}, not {STATUS_PENDING}."
                )

            decided = replace(
                request,
                status=outcome,
                approver=approver,
                reason=reason,
                decided_at=datetime.now(timezone.utc),
            )

            self._requests_by_id[request_id] = decided

            return decided

    def _resolve(self, request_id: str) -> ExecutionApprovalRequest:
        request = self._requests_by_id.get(request_id)

        if request is None:
            raise ExecutionApprovalError(f"No request is recorded under request ID {request_id!r}.")

        return request

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionApprovalError(f"Cannot use an empty or blank {field_name}.")
