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

from .execution_approval_delegation import (
    ExecutionApprovalDelegation,
)

from .execution_approval_delegation_error import (
    ExecutionApprovalDelegationError,
)


class ExecutionApprovalDelegationService:
    """
    Lets an approver delegate their approval authority to another
    identity for a scoped action, without ever replacing the
    approver on an approval request's own audit record: authorize()
    only confirms whether a delegate may act, and hands back the
    delegation (and its approver) so a caller can still record the
    original approver on the underlying approval request.

    Behavior:
    - delegate() always requires a non-None expires_at; a delegation
      with no expiry can never be created
    - A delegation is active only while it is enabled and not past
      its expires_at; revoking or letting it expire never deletes its
      record
    - authorize() only succeeds against an active delegation whose
      scope matches the approval request's action; a revoked,
      expired, or scope-mismatched delegation immediately fails
    - active() lists only the delegations currently active for an
      approver

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, approval_request_service):
        """
        Args:
            approval_request_service: The service used to resolve an
                approval request's action. Any object exposing
                `find(request_id)`, returning an object with an
                `action` attribute, is accepted
        """

        if approval_request_service is None:
            raise ExecutionApprovalDelegationError(
                "Cannot initialize execution approval delegation service with a None approval request service."
            )

        self._approval_request_service = approval_request_service
        self._delegations_by_id = {}
        self._delegation_ids_by_approver = {}
        self._delegation_ids_by_delegate = {}
        self._lock = RLock()

    def delegate(
        self,
        approver: str,
        delegate: str,
        scope: str,
        expires_at: datetime,
    ) -> ExecutionApprovalDelegation:
        """
        Grant a new, active delegation.

        Raises:
            ExecutionApprovalDelegationError: If approver, delegate,
                or scope is None or blank, or expires_at is None
        """

        with self._lock:
            delegation = ExecutionApprovalDelegation(
                delegation_id=str(uuid4()),
                approver=approver,
                delegate=delegate,
                scope=scope,
                expires_at=expires_at,
            )

            self._delegations_by_id[delegation.delegation_id] = delegation
            self._delegation_ids_by_approver.setdefault(approver, []).append(delegation.delegation_id)
            self._delegation_ids_by_delegate.setdefault(delegate, []).append(delegation.delegation_id)

            return delegation

    def revoke(self, delegation_id: str) -> ExecutionApprovalDelegation:
        """
        Revoke a delegation, so it is inactive immediately, even if
        it has not yet expired.

        Raises:
            ExecutionApprovalDelegationError: If delegation_id is
                None or blank, or no delegation is recorded under it
        """

        self._validate_text(delegation_id, "delegation ID")

        with self._lock:
            delegation = self._resolve(delegation_id)

            updated = replace(delegation, enabled=False)
            self._delegations_by_id[delegation_id] = updated

            return updated

    def authorize(self, delegate: str, request_id: str) -> ExecutionApprovalDelegation:
        """
        Check whether a delegate holds an active delegation whose
        scope matches an approval request's action, and hand back
        that delegation.

        Raises:
            ExecutionApprovalDelegationError: If delegate or
                request_id is None or blank, the request cannot be
                resolved, or no active delegation with a matching
                scope is found for the delegate
        """

        self._validate_text(delegate, "delegate")
        self._validate_text(request_id, "request ID")

        with self._lock:
            request = self._approval_request_service.find(request_id)

            if request is None:
                raise ExecutionApprovalDelegationError(
                    f"Cannot authorize delegate {delegate!r}: no approval request is recorded under request ID {request_id!r}."
                )

            for delegation_id in self._delegation_ids_by_delegate.get(delegate, []):
                delegation = self._delegations_by_id[delegation_id]

                if delegation.scope != request.action:
                    continue

                if self._is_active(delegation):
                    return delegation

            raise ExecutionApprovalDelegationError(
                f"Cannot authorize delegate {delegate!r} for request ID {request_id!r}: "
                f"no active delegation authorizes scope {request.action!r}."
            )

    def active(self, approver: str) -> list:
        """
        List the currently active delegations granted by an approver.

        Raises:
            ExecutionApprovalDelegationError: If approver is None or
                blank
        """

        self._validate_text(approver, "approver")

        with self._lock:
            return [
                self._delegations_by_id[delegation_id]
                for delegation_id in self._delegation_ids_by_approver.get(approver, [])
                if self._is_active(self._delegations_by_id[delegation_id])
            ]

    def _is_active(self, delegation: ExecutionApprovalDelegation) -> bool:
        if not delegation.enabled:
            return False

        return delegation.expires_at > datetime.now(timezone.utc)

    def _resolve(self, delegation_id: str) -> ExecutionApprovalDelegation:
        delegation = self._delegations_by_id.get(delegation_id)

        if delegation is None:
            raise ExecutionApprovalDelegationError(f"No delegation is recorded under delegation ID {delegation_id!r}.")

        return delegation

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionApprovalDelegationError(f"Cannot use an empty or blank {field_name}.")
