from datetime import (
    datetime,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_certification_validity import (
    STATUS_ACTIVE,
)

from .execution_compliance_renewal import (
    ExecutionComplianceRenewal,
)

from .execution_compliance_renewal_error import (
    ExecutionComplianceRenewalError,
)


class ExecutionComplianceRenewalService:
    """
    Lets an authorized reviewer renew a still-active, non-revoked
    certification's validity period after review, without ever
    losing an earlier renewal's history.

    It operates over a certification validity service supplied at
    construction time to confirm a certification is currently
    ACTIVE, and to read its current expiry, before a renewal can be
    recorded; it never checks, expires, or invalidates a
    certification itself. Which reviewers are authorized to renew is
    fixed at construction time.

    Behavior:
    - renew() only succeeds for a reviewer in the authorized set,
      against a certification whose validity is currently ACTIVE
      (never EXPIRED or INVALIDATED), and only with a new expiry
      strictly later than the certification's current expiry
    - Every renewal is retained; renewing again never edits or
      removes an earlier renewal record

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, validity_service, authorized_reviewers):
        """
        Args:
            validity_service: The service used to confirm a
                certification is currently ACTIVE and to read its
                current expiry. Any object exposing
                `check(certification_id)`, returning an object with
                `status` and `expires_at` attributes (or raising if
                the certification is unknown), is accepted
            authorized_reviewers: The identifiers of reviewers
                permitted to renew

        Raises:
            ExecutionComplianceRenewalError: If validity_service or
                authorized_reviewers is None
        """

        if validity_service is None:
            raise ExecutionComplianceRenewalError(
                "Cannot initialize execution compliance renewal service with a None validity service."
            )

        if authorized_reviewers is None:
            raise ExecutionComplianceRenewalError(
                "Cannot initialize execution compliance renewal service with None authorized_reviewers."
            )

        self._validity_service = validity_service
        self._authorized_reviewers = frozenset(authorized_reviewers)
        self._renewal_ids_by_certification = {}
        self._renewals_by_id = {}
        self._lock = RLock()

    def renew(
        self,
        certification_id: str,
        reviewer: str,
        expires_at: datetime,
    ) -> ExecutionComplianceRenewal:
        """
        Renew a currently active certification's validity period.

        Raises:
            ExecutionComplianceRenewalError: If certification_id or
                reviewer is None or blank, reviewer is not
                authorized, the certification's validity is not
                currently ACTIVE, or expires_at is not later than the
                certification's current expiry
        """

        self._validate_text(certification_id, "certification ID")
        self._validate_text(reviewer, "reviewer")

        with self._lock:
            if reviewer not in self._authorized_reviewers:
                raise ExecutionComplianceRenewalError(
                    f"Cannot renew: reviewer {reviewer!r} is not an authorized reviewer."
                )

            validity = self._validity_service.check(certification_id)

            if validity.status != STATUS_ACTIVE:
                raise ExecutionComplianceRenewalError(
                    f"Cannot renew certification ID {certification_id!r}: it is {validity.status}, not {STATUS_ACTIVE}."
                )

            renewal = ExecutionComplianceRenewal(
                renewal_id=str(uuid4()),
                certification_id=certification_id,
                reviewer=reviewer,
                previous_expiry=validity.expires_at,
                new_expiry=expires_at,
            )

            self._renewals_by_id[renewal.renewal_id] = renewal
            self._renewal_ids_by_certification.setdefault(certification_id, []).append(renewal.renewal_id)

            return renewal

    def eligible(self, certification_id: str) -> bool:
        """
        Whether a certification is currently renewable, i.e. its
        validity is ACTIVE.

        Raises:
            ExecutionComplianceRenewalError: If certification_id is
                None or blank
        """

        self._validate_text(certification_id, "certification ID")

        return self._validity_service.check(certification_id).status == STATUS_ACTIVE

    def history(self, certification_id: str) -> tuple:
        """
        List every renewal recorded for a certification, in the
        order renew() produced them.

        Raises:
            ExecutionComplianceRenewalError: If certification_id is
                None or blank
        """

        self._validate_text(certification_id, "certification ID")

        with self._lock:
            return tuple(
                self._renewals_by_id[renewal_id]
                for renewal_id in self._renewal_ids_by_certification.get(certification_id, [])
            )

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionComplianceRenewalError(f"Cannot use an empty or blank {field_name}.")
