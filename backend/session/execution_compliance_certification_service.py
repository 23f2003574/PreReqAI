from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_compliance_attestation import (
    DECISION_ACCEPT,
)

from .execution_compliance_certification import (
    ExecutionComplianceCertification,
    STATUS_CERTIFIED,
    STATUS_FAILED,
    STATUS_REVOKED,
)

from .execution_compliance_certification_error import (
    ExecutionComplianceCertificationError,
)

from .execution_compliance_rule import (
    SEVERITY_BLOCKING,
)


class ExecutionComplianceCertificationService:
    """
    Produces a final certification showing whether a change request
    satisfies every required compliance control, by weighing an
    existing compliance service, exception service, and attestation
    service together.

    It operates over those three services supplied at construction
    time to resolve a change request's currently enabled rules and
    violations, active exceptions, and accepted attestations; it
    never registers rules, records evidence, grants exceptions, or
    attests itself.

    Behavior:
    - certify() always records a new certification: CERTIFIED if
      every BLOCKING rule either has no violation or an active
      exception covering it, and every BLOCKING rule has at least one
      ACCEPT attestation; FAILED otherwise
    - An active exception for a violated BLOCKING rule counts as a
      valid override of that violation, but never waives the
      requirement for an ACCEPT attestation on that rule
    - A certification's own fields never change once recorded;
      revoke() only ever produces a new, superseding record
    - Only a CERTIFIED record can be revoked, and only with a
      non-blank reason

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, compliance_service, exception_service, attestation_service):
        """
        Args:
            compliance_service: The service used to resolve a change
                request's currently enabled rules and violations. Any
                object exposing `rules()`, returning an iterable of
                objects with `rule_id` and `severity` attributes, and
                `evaluate(change_id)`, returning an iterable of
                mappings with `rule_id` and `severity` keys, is
                accepted
            exception_service: The service used to resolve a change
                request's currently active exceptions. Any object
                exposing `active(change_id)`, returning an iterable of
                objects with a `rule_id` attribute, is accepted
            attestation_service: The service used to resolve the
                attestations recorded for a rule. Any object exposing
                `for_rule(change_id, rule_id)`, returning an iterable
                of objects with `attestation_id` and `decision`
                attributes, is accepted
        """

        for name, service in (
            ("compliance_service", compliance_service),
            ("exception_service", exception_service),
            ("attestation_service", attestation_service),
        ):
            if service is None:
                raise ExecutionComplianceCertificationError(
                    f"Cannot initialize execution compliance certification service with a None {name}."
                )

        self._compliance_service = compliance_service
        self._exception_service = exception_service
        self._attestation_service = attestation_service
        self._certifications_by_id = {}
        self._certification_ids_by_change = {}
        self._lock = RLock()

    def certify(self, change_id: str) -> ExecutionComplianceCertification:
        """
        Weigh a change request's current rules, violations,
        exceptions, and attestations into a new certification record.

        Raises:
            ExecutionComplianceCertificationError: If change_id is
                None or blank
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            rules = tuple(self._compliance_service.rules())
            rules_checked = tuple(sorted(rule.rule_id for rule in rules))
            blocking_rule_ids = {rule.rule_id for rule in rules if rule.severity == SEVERITY_BLOCKING}

            violations = tuple(self._compliance_service.evaluate(change_id))
            violated_blocking_rule_ids = {
                violation["rule_id"] for violation in violations if violation["severity"] == SEVERITY_BLOCKING
            }

            excepted_rule_ids = {
                exception.rule_id for exception in self._exception_service.active(change_id)
            }

            unresolved_violations = violated_blocking_rule_ids - excepted_rule_ids

            attestation_ids = set()
            missing_attestations = set()

            for rule_id in blocking_rule_ids:
                attestations = tuple(self._attestation_service.for_rule(change_id, rule_id))

                if not any(attestation.decision == DECISION_ACCEPT for attestation in attestations):
                    missing_attestations.add(rule_id)

                attestation_ids.update(attestation.attestation_id for attestation in attestations)

            status = STATUS_FAILED if (unresolved_violations or missing_attestations) else STATUS_CERTIFIED

            certification = ExecutionComplianceCertification(
                certification_id=str(uuid4()),
                change_id=change_id,
                status=status,
                rules_checked=rules_checked,
                attestations=tuple(sorted(attestation_ids)),
            )

            self._certifications_by_id[certification.certification_id] = certification
            self._certification_ids_by_change.setdefault(change_id, []).append(certification.certification_id)

            return certification

    def status(self, change_id: str) -> str:
        """
        The status of the most recently recorded certification for a
        change request.

        Raises:
            ExecutionComplianceCertificationError: If change_id is
                None or blank, or the change request has never been
                certified
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            ids = self._certification_ids_by_change.get(change_id)

            if not ids:
                raise ExecutionComplianceCertificationError(
                    f"Cannot get status for change ID {change_id!r}: it has never been certified."
                )

            return self._certifications_by_id[ids[-1]].status

    def history(self, change_id: str) -> tuple:
        """
        List every certification recorded for a change request, in
        the order certify() produced them, reflecting any
        subsequent revocation.

        Raises:
            ExecutionComplianceCertificationError: If change_id is
                None or blank
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            return tuple(
                self._certifications_by_id[certification_id]
                for certification_id in self._certification_ids_by_change.get(change_id, [])
            )

    def revoke(self, certification_id: str, reason: str) -> ExecutionComplianceCertification:
        """
        Revoke a certified record.

        Raises:
            ExecutionComplianceCertificationError: If certification_id
                or reason is None or blank, no certification is
                recorded under certification_id, or it is not
                currently CERTIFIED
        """

        self._validate_text(certification_id, "certification ID")
        self._validate_text(reason, "reason")

        with self._lock:
            certification = self._certifications_by_id.get(certification_id)

            if certification is None:
                raise ExecutionComplianceCertificationError(
                    f"No certification is recorded under certification ID {certification_id!r}."
                )

            if certification.status != STATUS_CERTIFIED:
                raise ExecutionComplianceCertificationError(
                    f"Cannot revoke certification ID {certification_id!r}: it is {certification.status}, "
                    f"not {STATUS_CERTIFIED}."
                )

            revoked = replace(certification, status=STATUS_REVOKED, reason=reason)
            self._certifications_by_id[certification_id] = revoked

            return revoked

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionComplianceCertificationError(f"Cannot use an empty or blank {field_name}.")
