from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_approval_quorum import (
    ExecutionApprovalQuorum,
    STATUS_PENDING,
    STATUS_SATISFIED,
)

from .execution_approval_quorum_error import (
    ExecutionApprovalQuorumError,
)


class ExecutionApprovalQuorumService:
    """
    Tracks independent approvals collected for an approval request
    that requires more than one approver before it may proceed.

    Behavior:
    - create() always starts a new quorum PENDING, with no approvers
      recorded and a required_count of at least 1
    - approve() records a unique approver; the same approver can
      never count more than once toward a quorum
    - A quorum's status becomes SATISFIED exactly when the number of
      unique approvers reaches required_count; the request it gates
      may proceed only once satisfied() reports True

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._quorums_by_id = {}
        self._lock = RLock()

    def create(self, request_id: str, required_count: int) -> ExecutionApprovalQuorum:
        """
        Create a new, pending quorum for an approval request.

        Raises:
            ExecutionApprovalQuorumError: If request_id is None or
                blank, or required_count is not an int of at least 1
        """

        with self._lock:
            quorum = ExecutionApprovalQuorum(
                quorum_id=str(uuid4()),
                request_id=request_id,
                required_count=required_count,
                approvers=(),
                status=STATUS_PENDING,
            )

            self._quorums_by_id[quorum.quorum_id] = quorum

            return quorum

    def approve(self, quorum_id: str, approver: str) -> ExecutionApprovalQuorum:
        """
        Record a unique approver's approval toward a quorum.

        Raises:
            ExecutionApprovalQuorumError: If quorum_id or approver is
                None or blank, no quorum is registered under
                quorum_id, or approver has already approved this
                quorum
        """

        self._validate_text(approver, "approver")

        with self._lock:
            quorum = self._resolve(quorum_id)

            if approver in quorum.approvers:
                raise ExecutionApprovalQuorumError(
                    f"Cannot approve quorum ID {quorum_id!r}: approver {approver!r} has already approved it."
                )

            approvers = quorum.approvers + (approver,)
            status = STATUS_SATISFIED if len(approvers) >= quorum.required_count else STATUS_PENDING

            updated = replace(quorum, approvers=approvers, status=status)
            self._quorums_by_id[quorum_id] = updated

            return updated

    def remaining(self, quorum_id: str) -> int:
        """
        The number of additional unique approvers still required to
        satisfy a quorum.

        Raises:
            ExecutionApprovalQuorumError: If quorum_id is None or
                blank, or no quorum is registered under it
        """

        self._validate_text(quorum_id, "quorum ID")

        with self._lock:
            quorum = self._resolve(quorum_id)

            return max(quorum.required_count - len(quorum.approvers), 0)

    def satisfied(self, quorum_id: str) -> bool:
        """
        Check whether a quorum has collected enough unique approvers
        for its request to proceed.

        Raises:
            ExecutionApprovalQuorumError: If quorum_id is None or
                blank, or no quorum is registered under it
        """

        self._validate_text(quorum_id, "quorum ID")

        with self._lock:
            return self._resolve(quorum_id).status == STATUS_SATISFIED

    def _resolve(self, quorum_id: str) -> ExecutionApprovalQuorum:
        self._validate_text(quorum_id, "quorum ID")

        quorum = self._quorums_by_id.get(quorum_id)

        if quorum is None:
            raise ExecutionApprovalQuorumError(f"No quorum is recorded under quorum ID {quorum_id!r}.")

        return quorum

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionApprovalQuorumError(f"Cannot use an empty or blank {field_name}.")
