from threading import (
    RLock,
)

from uuid import uuid4

from .execution_change_validation import (
    ExecutionChangeValidation,
)

from .execution_change_validation_error import (
    ExecutionChangeValidationError,
)

PROTECTED_KEYS = frozenset(
    {
        "safety_lock",
        "audit_logging",
        "governance_mode",
    }
)


class ExecutionChangeValidationService:
    """
    Validates a change request's proposed configuration changes
    against governance rules, so an invalid change request can be
    identified and blocked before it is approved or applied.

    It operates over a change request service supplied at
    construction time to resolve a change request's proposed changes;
    it never approves, rejects, or applies a change request itself.

    Behavior:
    - validate() always checks every key in a change request's
      proposed changes, never stopping at the first violation, and
      records a new, immutable ExecutionChangeValidation
    - A change request that changes or deletes a protected key (see
      PROTECTED_KEYS) is invalid; every protected key touched is
      reported as its own violation
    - can_approve() reflects only the most recently recorded
      validation for a change request: an invalid change request can
      never be approved
    - revalidate() re-reads the change request's current proposed
      changes and re-runs the rules, so edits made after an earlier,
      invalid validation can be checked again

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, change_request_service):
        """
        Args:
            change_request_service: The service used to resolve a
                change request's proposed changes. Any object
                exposing `find(change_id)`, returning an object with
                a `changes` mapping attribute, is accepted
        """

        if change_request_service is None:
            raise ExecutionChangeValidationError(
                "Cannot initialize execution change validation service with a None change request service."
            )

        self._change_request_service = change_request_service
        self._latest_by_change = {}
        self._lock = RLock()

    def validate(self, change_id: str) -> ExecutionChangeValidation:
        """
        Run the governance rules against a change request's currently
        proposed changes and record the result.

        Raises:
            ExecutionChangeValidationError: If change_id is None or
                blank, or no change request is resolvable under it
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            request = self._change_request_service.find(change_id)

            if request is None:
                raise ExecutionChangeValidationError(
                    f"Cannot validate change ID {change_id!r}: no change request is registered under it."
                )

            violations = tuple(
                f"protected_key_changed:{key}" for key in request.changes if key in PROTECTED_KEYS
            )

            validation = ExecutionChangeValidation(
                validation_id=str(uuid4()),
                change_id=change_id,
                valid=not violations,
                violations=violations,
            )

            self._latest_by_change[change_id] = validation

            return validation

    def violations(self, change_id: str) -> tuple:
        """
        The violations found by the most recent validation of a
        change request.

        Raises:
            ExecutionChangeValidationError: If change_id is None or
                blank, or the change request has never been validated
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            return self._resolve(change_id).violations

    def revalidate(self, change_id: str) -> ExecutionChangeValidation:
        """
        Re-run validation for a change request, reflecting any edits
        made to its proposed changes since it was last validated.

        Raises:
            ExecutionChangeValidationError: If change_id is None or
                blank, or no change request is resolvable under it
        """

        return self.validate(change_id)

    def can_approve(self, change_id: str) -> bool:
        """
        Whether a change request's most recent validation found it
        valid: an invalid change request can never be approved.

        Raises:
            ExecutionChangeValidationError: If change_id is None or
                blank, or the change request has never been validated
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            return self._resolve(change_id).valid

    def _resolve(self, change_id: str) -> ExecutionChangeValidation:
        validation = self._latest_by_change.get(change_id)

        if validation is None:
            raise ExecutionChangeValidationError(
                f"Cannot operate on change ID {change_id!r}: it has never been validated."
            )

        return validation

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionChangeValidationError(f"Cannot use an empty or blank {field_name}.")
