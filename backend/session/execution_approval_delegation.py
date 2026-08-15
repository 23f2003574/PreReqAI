from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from .execution_approval_delegation_error import (
    ExecutionApprovalDelegationError,
)


@dataclass(frozen=True)
class ExecutionApprovalDelegation:
    """
    Immutable record granting a delegate authority to act as an
    approver for approval requests within a scope, until expires_at
    or revocation.

    The delegation is a value object only. It never approves or
    rejects an approval request itself, and it never replaces the
    original approver on a request's audit record; granting,
    revoking, and authorizing against delegations is the
    responsibility of an execution approval delegation service.

    Attributes:
        delegation_id: The delegation's unique identifier
        approver: The identifier of the approver granting their
            authority away
        delegate: The identifier of who receives the authority
        scope: The action this delegation authorizes the delegate to
            approve on the approver's behalf
        expires_at: When this delegation stops applying. Required: a
            delegation with no expiry can never be created
        enabled: Whether this delegation is currently in force; a
            revoked delegation is inactive immediately, even before
            expires_at
    """

    delegation_id: str

    approver: str

    delegate: str

    scope: str

    expires_at: datetime

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.delegation_id, "delegation ID")
        self._require_text(self.approver, "approver")
        self._require_text(self.delegate, "delegate")
        self._require_text(self.scope, "scope")

        if not isinstance(self.expires_at, datetime):
            raise ExecutionApprovalDelegationError(
                "Cannot build an execution approval delegation with no expires_at."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionApprovalDelegationError(
                "Cannot build an execution approval delegation with a non-bool enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionApprovalDelegationError(
                f"Cannot build an execution approval delegation with an empty or blank {field_name}."
            )
