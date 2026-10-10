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

from .execution_change_request import (
    ExecutionChangeRequest,
    STATUS_APPLIED,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
)

from .execution_change_request_error import (
    ExecutionChangeRequestError,
)


class ExecutionChangeRequestService:
    """
    Requires controlled, approved change requests before a session's
    governed execution configuration may be modified.

    Behavior:
    - create() always starts a new request as PENDING
    - Only a PENDING request can be approved or rejected; only an
      APPROVED request can be applied. A rejected request can never
      apply, and a request can never be decided or applied twice
    - apply() applies every key in a request's changes to the
      session's configuration atomically: either every change takes
      effect, or, if any one of them is invalid at apply time (for
      example, deleting a key that no longer exists), none of them
      do and the request remains APPROVED for a retry

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._requests_by_id = {}
        self._config_by_session = {}
        self._lock = RLock()

    def create(
        self,
        session_id: str,
        changes,
        requester: str,
    ) -> ExecutionChangeRequest:
        """
        Create a new, pending change request.

        Raises:
            ExecutionChangeRequestError: If session_id or requester is
                None or blank, or changes is None or empty
        """

        with self._lock:
            request = ExecutionChangeRequest(
                change_id=str(uuid4()),
                session_id=session_id,
                requested_by=requester,
                changes=changes,
                status=STATUS_PENDING,
            )

            self._requests_by_id[request.change_id] = request

            return request

    def approve(self, change_id: str, approver: str) -> ExecutionChangeRequest:
        """
        Approve a pending change request.

        Raises:
            ExecutionChangeRequestError: If change_id or approver is
                None or blank, no request is registered under
                change_id, or the request is not pending
        """

        self._validate_text(approver, "approver")

        with self._lock:
            request = self._resolve(change_id)

            if request.status != STATUS_PENDING:
                raise ExecutionChangeRequestError(
                    f"Cannot approve change ID {change_id!r}: it is {request.status}, not {STATUS_PENDING}."
                )

            updated = replace(
                request,
                status=STATUS_APPROVED,
                approver=approver,
                decided_at=datetime.now(timezone.utc),
            )

            self._requests_by_id[change_id] = updated

            return updated

    def reject(self, change_id: str, approver: str, reason: str) -> ExecutionChangeRequest:
        """
        Reject a pending change request.

        Raises:
            ExecutionChangeRequestError: If change_id, approver, or
                reason is None or blank, no request is registered
                under change_id, or the request is not pending
        """

        self._validate_text(approver, "approver")
        self._validate_text(reason, "reason")

        with self._lock:
            request = self._resolve(change_id)

            if request.status != STATUS_PENDING:
                raise ExecutionChangeRequestError(
                    f"Cannot reject change ID {change_id!r}: it is {request.status}, not {STATUS_PENDING}."
                )

            updated = replace(
                request,
                status=STATUS_REJECTED,
                approver=approver,
                reason=reason,
                decided_at=datetime.now(timezone.utc),
            )

            self._requests_by_id[change_id] = updated

            return updated

    def apply(self, change_id: str) -> ExecutionChangeRequest:
        """
        Apply an approved change request's changes to its session's
        configuration, atomically.

        Raises:
            ExecutionChangeRequestError: If change_id is None or
                blank, no request is registered under it, the request
                is not approved, or any of its changes is invalid at
                apply time (in which case none of them are applied)
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            request = self._resolve(change_id)

            if request.status != STATUS_APPROVED:
                raise ExecutionChangeRequestError(
                    f"Cannot apply change ID {change_id!r}: it is {request.status}, not {STATUS_APPROVED}."
                )

            config = dict(self._config_by_session.get(request.session_id, {}))

            for key, value in request.changes.items():
                if value is None:
                    if key not in config:
                        raise ExecutionChangeRequestError(
                            f"Cannot apply change ID {change_id!r}: key {key!r} does not exist to delete."
                        )

                    del config[key]
                else:
                    config[key] = value

            self._config_by_session[request.session_id] = config

            updated = replace(
                request,
                status=STATUS_APPLIED,
                applied_at=datetime.now(timezone.utc),
            )

            self._requests_by_id[change_id] = updated

            return updated

    def status(self, change_id: str) -> str:
        """
        Look up a change request's current status.

        Raises:
            ExecutionChangeRequestError: If change_id is None or
                blank, or no request is registered under it
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            return self._resolve(change_id).status

    def configuration(self, session_id: str) -> dict:
        """
        The current, applied configuration for a session.

        Raises:
            ExecutionChangeRequestError: If session_id is None or
                blank
        """

        self._validate_text(session_id, "session ID")

        with self._lock:
            return dict(self._config_by_session.get(session_id, {}))

    def _resolve(self, change_id: str) -> ExecutionChangeRequest:
        self._validate_text(change_id, "change ID")

        request = self._requests_by_id.get(change_id)

        if request is None:
            raise ExecutionChangeRequestError(f"No request is recorded under change ID {change_id!r}.")

        return request

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionChangeRequestError(f"Cannot use an empty or blank {field_name}.")
