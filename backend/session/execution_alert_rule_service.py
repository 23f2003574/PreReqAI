from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_observability_alert_rule import (
    ExecutionObservabilityAlertRule,
    OPERATOR_EQ,
    OPERATOR_GT,
    OPERATOR_GTE,
    OPERATOR_LT,
    OPERATOR_LTE,
)

from .execution_observability_alert_rule_error import (
    ExecutionObservabilityAlertRuleError,
)

_COMPARATORS = {
    OPERATOR_GT: lambda value, threshold: value > threshold,
    OPERATOR_GTE: lambda value, threshold: value >= threshold,
    OPERATOR_LT: lambda value, threshold: value < threshold,
    OPERATOR_LTE: lambda value, threshold: value <= threshold,
    OPERATOR_EQ: lambda value, threshold: value == threshold,
}


class ExecutionAlertRuleService:
    """
    Registers alert rules and evaluates them against current
    observability data, turning abnormal runtime metrics into
    actionable alerts.

    Composes with an existing metrics service (anything exposing
    `latest(runtime_id, name)` -> object with `.value`, matching
    ExecutionMetricsService), used to read a runtime's current metric
    values. Performs no recording of its own or mutation of the
    composed service; every read is a pure lookup.

    Behavior:
    - register() stores a rule, keyed by rule_id; registering under
      an already-used rule_id replaces the prior rule
    - evaluate() checks every enabled registered rule against
      runtime_id's latest recorded value for that rule's metric, and
      returns the rules whose condition currently holds; disabled
      rules and rules with no recorded metric are skipped
    - violations() reports the same currently-triggered rules as
      evaluate()
    - disable() is idempotent: disabling an already-disabled rule
      simply returns it unchanged
    - rules() reports every registered rule, in registration order

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, metrics_service):
        self._metrics_service = metrics_service
        self._rules_by_id = {}
        self._lock = RLock()

    def register(self, rule: ExecutionObservabilityAlertRule) -> ExecutionObservabilityAlertRule:
        """
        Register (or replace) an alert rule.

        Raises:
            ExecutionObservabilityAlertRuleError: If rule is not an
                ExecutionObservabilityAlertRule
        """

        if not isinstance(rule, ExecutionObservabilityAlertRule):
            raise ExecutionObservabilityAlertRuleError(
                "Cannot register an object that is not an ExecutionObservabilityAlertRule."
            )

        with self._lock:
            self._rules_by_id[rule.rule_id] = rule

            return rule

    def evaluate(self, runtime_id: str) -> tuple:
        """
        Every enabled registered rule whose condition currently holds
        for runtime_id, in registration order.

        Raises:
            ExecutionObservabilityAlertRuleError: If runtime_id is
                None or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            candidates = list(self._rules_by_id.values())

        triggered = []

        for rule in candidates:
            if not rule.enabled:
                continue

            latest = self._metrics_service.latest(runtime_id, rule.metric)

            if latest is None:
                continue

            if _COMPARATORS[rule.operator](latest.value, rule.threshold):
                triggered.append(rule)

        return tuple(triggered)

    def violations(self, runtime_id: str) -> tuple:
        """
        The rules currently violated for runtime_id (an alias for
        evaluate()).

        Raises:
            ExecutionObservabilityAlertRuleError: If runtime_id is
                None or blank
        """

        return self.evaluate(runtime_id)

    def disable(self, rule_id: str) -> ExecutionObservabilityAlertRule:
        """
        Disable a registered rule. Idempotent: disabling an
        already-disabled rule simply returns it unchanged.

        Raises:
            ExecutionObservabilityAlertRuleError: If rule_id is None
                or blank, or no rule is registered under it
        """

        self._validate_text(rule_id, "rule ID")

        with self._lock:
            rule = self._resolve(rule_id)

            if not rule.enabled:
                return rule

            disabled = replace(rule, enabled=False)
            self._rules_by_id[rule_id] = disabled

            return disabled

    def rules(self) -> tuple:
        """
        Every registered rule, in registration order.
        """

        with self._lock:
            return tuple(self._rules_by_id.values())

    def _resolve(self, rule_id: str) -> ExecutionObservabilityAlertRule:
        rule = self._rules_by_id.get(rule_id)

        if rule is None:
            raise ExecutionObservabilityAlertRuleError(
                f"No rule is registered under rule ID {rule_id!r}."
            )

        return rule

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityAlertRuleError(f"Cannot use an empty or blank {field_name}.")
