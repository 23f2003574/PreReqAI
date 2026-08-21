from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_observability_alert_correlation_error import (
    ExecutionObservabilityAlertCorrelationError,
)

from .execution_observability_decision import (
    ExecutionObservabilityDecision,
    STATUS_CRITICAL,
    STATUS_HEALTHY,
    STATUS_WARNING,
)

from .execution_observability_decision_error import (
    ExecutionObservabilityDecisionError,
)

_LEVEL_CRITICAL = "CRITICAL"


class ExecutionObservabilityOrchestrationService:
    """
    Unifies metrics, events, traces, alert rules, alerts, escalation,
    suppression, routing, deduplication, correlation, and analytics
    into one observability pipeline for a runtime.

    Composes with an existing instance of every earlier observability
    component (duck-typed to what each already exposes):
        metrics_service: all(runtime_id) (ExecutionMetricsService)
        event_service: history(runtime_id) (ExecutionEventService)
        trace_service: history(runtime_id) (ExecutionTraceService)
        alert_rule_service: evaluate(runtime_id)
            (ExecutionAlertRuleService)
        alert_service: trigger(runtime_id, rule_id), active(runtime_id),
            all_active() (ExecutionAlertService)
        escalation_service: evaluate(alert_id), escalate(alert_id),
            level(alert_id) (ExecutionAlertEscalationService)
        suppression_service: is_suppressed(rule_id, runtime_id)
            (ExecutionAlertSuppressionService)
        routing_service: resolve(alert_id) (ExecutionAlertRoutingService)
        deduplication_service: duplicate(alert), record(alert)
            (ExecutionAlertDeduplicationService)
        correlation_service: correlate(alert_ids)
            (ExecutionAlertCorrelationService)
        analytics_service: generate(runtime_id)
            (ExecutionAlertAnalyticsService)

    It performs no independent bookkeeping of its own: every fact it
    reports comes from calling into the composed components, which
    remain the source of truth.

    Behavior:
    - collect() is a pure read: it returns a runtime's current
      metrics, events, and traces exactly as their own services
      report them
    - evaluate() runs one pipeline cycle: it evaluates active alert
      rules, skips any rule currently suppressed for the runtime,
      triggers an alert for every remaining triggered rule, records
      it for deduplication (skipping routing, escalation, and
      correlation for anything flagged as a duplicate), resolves a
      route for each new alert, escalates it if its severity
      currently warrants that, and correlates it with any other
      currently-OPEN alert (on any runtime) sharing the same rule
    - alerts() is a pure read: a runtime's currently-OPEN alerts
    - summary() is a pure read: a runtime's current analytics plus
      the escalation levels active on its currently-OPEN alerts
    - decision() is a pure read, and is deterministic: calling it
      again without an intervening evaluate() call always reports the
      same status, alert_count, and health_summary content. status is
      CRITICAL if any currently-OPEN alert is escalated to CRITICAL
      or is ERROR severity, WARNING if any alert is OPEN at all, and
      HEALTHY otherwise
    """

    def __init__(
        self,
        metrics_service,
        event_service,
        trace_service,
        alert_rule_service,
        alert_service,
        escalation_service,
        suppression_service,
        routing_service,
        deduplication_service,
        correlation_service,
        analytics_service,
    ):
        self._metrics_service = metrics_service
        self._event_service = event_service
        self._trace_service = trace_service
        self._alert_rule_service = alert_rule_service
        self._alert_service = alert_service
        self._escalation_service = escalation_service
        self._suppression_service = suppression_service
        self._routing_service = routing_service
        self._deduplication_service = deduplication_service
        self._correlation_service = correlation_service
        self._analytics_service = analytics_service

    def collect(self, runtime_id: str) -> dict:
        """
        runtime_id's current metrics, events, and traces.

        Raises:
            ExecutionObservabilityDecisionError: If runtime_id is
                None or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        return {
            "metrics": self._metrics_service.all(runtime_id),
            "events": self._event_service.history(runtime_id),
            "traces": self._trace_service.history(runtime_id),
        }

    def evaluate(self, runtime_id: str) -> dict:
        """
        Run one alerting pipeline cycle for runtime_id: evaluate
        active rules, apply suppression and deduplication, route,
        escalate, and correlate whatever new alerts result.

        Raises:
            ExecutionObservabilityDecisionError: If runtime_id is
                None or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        new_alerts = []
        duplicate_alerts = []
        suppressed_rule_ids = []
        routes = {}
        escalations = {}
        correlations = []

        for rule in self._alert_rule_service.evaluate(runtime_id):
            if self._suppression_service.is_suppressed(rule.rule_id, runtime_id):
                suppressed_rule_ids.append(rule.rule_id)
                continue

            alert = self._alert_service.trigger(runtime_id, rule.rule_id)

            is_duplicate = self._deduplication_service.duplicate(alert)
            self._deduplication_service.record(alert)

            if is_duplicate:
                duplicate_alerts.append(alert)
                continue

            new_alerts.append(alert)

            route = self._routing_service.resolve(alert.alert_id)

            if route is not None:
                routes[alert.alert_id] = route

            if self._escalation_service.evaluate(alert.alert_id) is not None:
                escalations[alert.alert_id] = self._escalation_service.escalate(alert.alert_id)

            related = [
                other.alert_id
                for other in self._alert_service.all_active()
                if other.rule_id == alert.rule_id and other.alert_id != alert.alert_id
            ]

            if related:
                try:
                    correlations.append(
                        self._correlation_service.correlate([alert.alert_id] + related)
                    )
                except ExecutionObservabilityAlertCorrelationError:
                    pass

        return {
            "new_alerts": tuple(new_alerts),
            "duplicate_alerts": tuple(duplicate_alerts),
            "suppressed_rule_ids": tuple(suppressed_rule_ids),
            "routes": routes,
            "escalations": escalations,
            "correlations": tuple(correlations),
        }

    def alerts(self, runtime_id: str) -> tuple:
        """
        runtime_id's currently-OPEN alerts.

        Raises:
            ExecutionObservabilityDecisionError: If runtime_id is
                None or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        return self._alert_service.active(runtime_id)

    def summary(self, runtime_id: str) -> dict:
        """
        runtime_id's current analytics plus the escalation levels
        active on its currently-OPEN alerts.

        Raises:
            ExecutionObservabilityDecisionError: If runtime_id is
                None or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        active_alerts = self._alert_service.active(runtime_id)

        escalation_levels = tuple(
            level
            for level in (self._escalation_service.level(alert.alert_id) for alert in active_alerts)
            if level is not None
        )

        return {
            "analytics": self._analytics_service.generate(runtime_id),
            "escalation_levels": escalation_levels,
        }

    def decision(self, runtime_id: str) -> ExecutionObservabilityDecision:
        """
        A single, deterministic verdict combining runtime_id's
        currently-OPEN alert count with its escalation and analytics
        summary.

        Raises:
            ExecutionObservabilityDecisionError: If runtime_id is
                None or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        active_alerts = self._alert_service.active(runtime_id)
        health_summary = self.summary(runtime_id)

        return ExecutionObservabilityDecision(
            runtime_id=runtime_id,
            status=self._derive_status(active_alerts, health_summary),
            alert_count=len(active_alerts),
            health_summary=health_summary,
            decision_id=str(uuid4()),
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _derive_status(active_alerts, health_summary) -> str:
        if _LEVEL_CRITICAL in health_summary["escalation_levels"]:
            return STATUS_CRITICAL

        if any(alert.severity == "ERROR" for alert in active_alerts):
            return STATUS_CRITICAL

        if active_alerts:
            return STATUS_WARNING

        return STATUS_HEALTHY

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityDecisionError(f"Cannot use an empty or blank {field_name}.")
