from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from .execution_certification_validity import (
    ExecutionCertificationValidity,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_INVALIDATED,
)

from .execution_certification_validity_error import (
    ExecutionCertificationValidityError,
)

from .execution_compliance_certification import (
    STATUS_CERTIFIED,
)


class ExecutionCertificationValidityService:
    """
    Tracks whether an existing compliance certification is still
    within its validity period and has not been invalidated by a
    policy or rule change, so an expired or invalidated certification
    can never authorize execution.

    It operates over a compliance certification service supplied at
    construction time to resolve a certification's change request and
    to confirm it was actually CERTIFIED; it never certifies, revokes,
    or otherwise modifies a compliance certification itself. A
    certification is tracked lazily: the first check(), expire(), or
    invalidate() call for a certification_id establishes its
    validity window as certified_at plus the validity period supplied
    at construction time.

    Behavior:
    - check() always reflects real time: an ACTIVE record whose
      expires_at has passed is reported (and recorded) as EXPIRED,
      even if expire() was never explicitly called
    - expire() and invalidate() only succeed against a currently
      ACTIVE record; a record already EXPIRED or INVALIDATED is
      terminal and can never transition again
    - invalidate() always requires a non-blank reason, whether the
      invalidation was manual or driven by a policy or rule change;
      expire() never records a reason
    - active() lists only the records currently ACTIVE for a change
      request, applying the same real-time expiry check as check()

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, certification_service, validity_period: timedelta):
        """
        Args:
            certification_service: The service used to resolve a
                certification's change request and status. Any
                object exposing `find(certification_id)`, returning
                None or an object with `change_id`, `status`, and
                `certified_at` attributes, is accepted
            validity_period: How long a certification remains valid
                after its certified_at, once tracked

        Raises:
            ExecutionCertificationValidityError: If
                certification_service is None or validity_period is
                not a timedelta
        """

        if certification_service is None:
            raise ExecutionCertificationValidityError(
                "Cannot initialize execution certification validity service with a None certification service."
            )

        if not isinstance(validity_period, timedelta):
            raise ExecutionCertificationValidityError(
                "Cannot initialize execution certification validity service with a non-timedelta validity_period."
            )

        self._certification_service = certification_service
        self._validity_period = validity_period
        self._records_by_id = {}
        self._lock = RLock()

    def check(self, certification_id: str) -> ExecutionCertificationValidity:
        """
        Get a certification's current validity, applying real-time
        expiry if its validity period has passed.

        Raises:
            ExecutionCertificationValidityError: If certification_id
                is None or blank, or no CERTIFIED compliance
                certification is resolvable under it
        """

        self._validate_text(certification_id, "certification ID")

        with self._lock:
            return self._current(certification_id)

    def expire(self, certification_id: str) -> ExecutionCertificationValidity:
        """
        Explicitly expire a currently active certification.

        Raises:
            ExecutionCertificationValidityError: If certification_id
                is None or blank, no CERTIFIED compliance
                certification is resolvable under it, or the record is
                not currently ACTIVE
        """

        self._validate_text(certification_id, "certification ID")

        with self._lock:
            record = self._current(certification_id)

            if record.status != STATUS_ACTIVE:
                raise ExecutionCertificationValidityError(
                    f"Cannot expire certification ID {certification_id!r}: it is {record.status}, not {STATUS_ACTIVE}."
                )

            updated = replace(
                record,
                status=STATUS_EXPIRED,
                invalidated_at=datetime.now(timezone.utc),
            )

            self._records_by_id[certification_id] = updated

            return updated

    def invalidate(self, certification_id: str, reason: str) -> ExecutionCertificationValidity:
        """
        Invalidate a currently active certification, whether by
        manual action or a policy or rule change.

        Raises:
            ExecutionCertificationValidityError: If certification_id
                or reason is None or blank, no CERTIFIED compliance
                certification is resolvable under it, or the record is
                not currently ACTIVE
        """

        self._validate_text(certification_id, "certification ID")
        self._validate_text(reason, "reason")

        with self._lock:
            record = self._current(certification_id)

            if record.status != STATUS_ACTIVE:
                raise ExecutionCertificationValidityError(
                    f"Cannot invalidate certification ID {certification_id!r}: it is {record.status}, not {STATUS_ACTIVE}."
                )

            updated = replace(
                record,
                status=STATUS_INVALIDATED,
                invalidated_at=datetime.now(timezone.utc),
                reason=reason,
            )

            self._records_by_id[certification_id] = updated

            return updated

    def active(self, change_id: str) -> list:
        """
        List the currently active validity records for a change
        request's certifications, applying the same real-time expiry
        check as check().

        Raises:
            ExecutionCertificationValidityError: If change_id is None
                or blank
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            active_records = []

            for certification_id in list(self._records_by_id.keys()):
                record = self._current(certification_id)

                if record.status != STATUS_ACTIVE:
                    continue

                certification = self._certification_service.find(certification_id)

                if certification is not None and certification.change_id == change_id:
                    active_records.append(record)

            return active_records

    def can_authorize(self, certification_id: str) -> bool:
        """
        Whether a certification is currently ACTIVE and may authorize
        execution.

        Raises:
            ExecutionCertificationValidityError: If certification_id
                is None or blank, or no CERTIFIED compliance
                certification is resolvable under it
        """

        return self.check(certification_id).status == STATUS_ACTIVE

    def _current(self, certification_id: str) -> ExecutionCertificationValidity:
        record = self._records_by_id.get(certification_id)

        if record is None:
            record = self._register(certification_id)

        if record.status == STATUS_ACTIVE and record.expires_at <= datetime.now(timezone.utc):
            record = replace(
                record,
                status=STATUS_EXPIRED,
                invalidated_at=datetime.now(timezone.utc),
            )

            self._records_by_id[certification_id] = record

        return record

    def _register(self, certification_id: str) -> ExecutionCertificationValidity:
        certification = self._certification_service.find(certification_id)

        if certification is None:
            raise ExecutionCertificationValidityError(
                f"Cannot track certification ID {certification_id!r}: no compliance certification is registered under it."
            )

        if certification.status != STATUS_CERTIFIED:
            raise ExecutionCertificationValidityError(
                f"Cannot track certification ID {certification_id!r}: it is {certification.status}, not {STATUS_CERTIFIED}."
            )

        record = ExecutionCertificationValidity(
            certification_id=certification_id,
            expires_at=certification.certified_at + self._validity_period,
        )

        self._records_by_id[certification_id] = record

        return record

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionCertificationValidityError(f"Cannot use an empty or blank {field_name}.")
