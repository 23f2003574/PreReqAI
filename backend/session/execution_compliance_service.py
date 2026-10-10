from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_compliance_error import (
    ExecutionComplianceError,
)

from .execution_compliance_rule import (
    ExecutionComplianceRule,
    SEVERITY_BLOCKING,
)


class ExecutionComplianceService:
    """
    Evaluates a change request's proposed configuration changes
    against a registry of reusable, organization-defined compliance
    rules.

    It operates over a change request service supplied at
    construction time to resolve a change request's proposed changes;
    it never approves, rejects, or applies a change request itself.

    Behavior:
    - evaluate() always runs every currently enabled rule, never
      stopping at the first violation; a disabled rule is skipped
      entirely, as if it were never registered
    - A rule's condition returning False against a change request's
      changes is a violation, carrying that rule's severity
    - can_approve() reflects only the most recent evaluation for a
      change request: a BLOCKING violation prevents approval; a
      WARNING violation does not

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
            raise ExecutionComplianceError(
                "Cannot initialize execution compliance service with a None change request service."
            )

        self._change_request_service = change_request_service
        self._rules_by_id = {}
        self._latest_violations_by_change = {}
        self._lock = RLock()

    def register(self, rule: ExecutionComplianceRule) -> ExecutionComplianceRule:
        """
        Register a new compliance rule.

        Raises:
            ExecutionComplianceError: If rule is not an
                ExecutionComplianceRule, or a rule is already
                registered under its rule_id
        """

        if not isinstance(rule, ExecutionComplianceRule):
            raise ExecutionComplianceError(
                "Cannot register an execution compliance rule: rule must be an ExecutionComplianceRule."
            )

        with self._lock:
            if rule.rule_id in self._rules_by_id:
                raise ExecutionComplianceError(
                    f"Cannot register rule ID {rule.rule_id!r}: a rule is already registered under it."
                )

            self._rules_by_id[rule.rule_id] = rule

            return rule

    def evaluate(self, change_id: str) -> tuple:
        """
        Run every enabled rule against a change request's currently
        proposed changes and record the result.

        Returns:
            A tuple of violation dicts, each with `rule_id`, `name`,
            and `severity` keys, one per violated enabled rule

        Raises:
            ExecutionComplianceError: If change_id is None or blank,
                or no change request is resolvable under it
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            request = self._change_request_service.find(change_id)

            if request is None:
                raise ExecutionComplianceError(
                    f"Cannot evaluate change ID {change_id!r}: no change request is registered under it."
                )

            violations = tuple(
                {
                    "rule_id": rule.rule_id,
                    "name": rule.name,
                    "severity": rule.severity,
                }
                for rule in self._rules_by_id.values()
                if rule.enabled and not rule.condition(request.changes)
            )

            self._latest_violations_by_change[change_id] = violations

            return violations

    def violations(self, change_id: str) -> tuple:
        """
        The violations found by the most recent evaluation of a
        change request.

        Raises:
            ExecutionComplianceError: If change_id is None or blank,
                or the change request has never been evaluated
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            return self._resolve_violations(change_id)

    def disable(self, rule_id: str) -> ExecutionComplianceRule:
        """
        Disable a rule, so future evaluations ignore it entirely.

        Raises:
            ExecutionComplianceError: If rule_id is None or blank, or
                no rule is registered under it
        """

        self._validate_text(rule_id, "rule ID")

        with self._lock:
            rule = self._resolve_rule(rule_id)

            updated = replace(rule, enabled=False)
            self._rules_by_id[rule_id] = updated

            return updated

    def can_approve(self, change_id: str) -> bool:
        """
        Whether a change request's most recent evaluation found no
        BLOCKING violations.

        Raises:
            ExecutionComplianceError: If change_id is None or blank,
                or the change request has never been evaluated
        """

        self._validate_text(change_id, "change ID")

        with self._lock:
            violations = self._resolve_violations(change_id)

            return not any(violation["severity"] == SEVERITY_BLOCKING for violation in violations)

    def _resolve_violations(self, change_id: str) -> tuple:
        if change_id not in self._latest_violations_by_change:
            raise ExecutionComplianceError(
                f"Cannot operate on change ID {change_id!r}: it has never been evaluated."
            )

        return self._latest_violations_by_change[change_id]

    def _resolve_rule(self, rule_id: str) -> ExecutionComplianceRule:
        rule = self._rules_by_id.get(rule_id)

        if rule is None:
            raise ExecutionComplianceError(f"No rule is registered under rule ID {rule_id!r}.")

        return rule

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionComplianceError(f"Cannot use an empty or blank {field_name}.")
