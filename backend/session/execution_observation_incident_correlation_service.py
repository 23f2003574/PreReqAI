from threading import (
    RLock,
)

from .execution_observation_correlation_rule_error import (
    ExecutionObservationCorrelationRuleError,
)

from .execution_observation_correlation_rule import (
    ExecutionObservationCorrelationRule,
)


class ExecutionObservationIncidentCorrelationService:
    """
    Automatically correlates a session's observation events into
    incidents, using configurable matching rules. Observation events
    and incidents are assumed to already exist; this service only
    reads events and opens or extends incidents through the injected
    services.

    Behavior:
    - evaluate() only considers ENABLED rules; a disabled rule never
      matches anything
    - matches() decides whether one rule matches one event, based
      solely on the rule being enabled and the event's event_type
      being one of the rule's event_types
    - Events matching a rule are grouped by session: evaluate()
      never mixes events from different sessions into one incident
    - The first time a rule matches events for a session, evaluate()
      opens a new incident for them; on a later evaluate() call, if
      that incident is still active, newly matching events are added
      to it instead of opening a second one
    - An incident's event_ids, and evaluate()'s own result list, are
      always ordered consistently: event_ids follow the session's
      chronological event history, and the result list follows rule
      registration order

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, event_service, incident_service):
        """
        Args:
            event_service: The service used to read a session's
                recorded observation events. Any object exposing
                `history(session_id)`, returning events with
                `event_id` and `event_type` attributes, is accepted
            incident_service: The service used to open and extend
                incidents. Any object exposing `open(session_id,
                event_ids, severity=...)`, `add(incident_id,
                event_id)`, and `active(session_id)` is accepted
        """

        self._event_service = event_service
        self._incident_service = incident_service
        self._rules_by_id = {}
        self._rule_ids_in_order = []
        self._incident_id_by_rule_and_session = {}
        self._lock = RLock()

    def register(self, rule: ExecutionObservationCorrelationRule) -> ExecutionObservationCorrelationRule:
        """
        Register a new correlation rule.

        Raises:
            ExecutionObservationCorrelationRuleError: If rule is not
                an ExecutionObservationCorrelationRule, or its rule
                ID is already registered
        """

        if not isinstance(rule, ExecutionObservationCorrelationRule):
            raise ExecutionObservationCorrelationRuleError(
                "Cannot register an invalid rule: rule must be an ExecutionObservationCorrelationRule."
            )

        with self._lock:
            if rule.rule_id in self._rules_by_id:
                raise ExecutionObservationCorrelationRuleError(f"Rule ID {rule.rule_id!r} is already registered.")

            self._rules_by_id[rule.rule_id] = rule
            self._rule_ids_in_order.append(rule.rule_id)

            return rule

    def matches(self, rule: ExecutionObservationCorrelationRule, event) -> bool:
        """
        Decide whether a rule matches an event.

        Raises:
            ExecutionObservationCorrelationRuleError: If rule is not
                an ExecutionObservationCorrelationRule
        """

        if not isinstance(rule, ExecutionObservationCorrelationRule):
            raise ExecutionObservationCorrelationRuleError(
                "Cannot match an invalid rule: rule must be an ExecutionObservationCorrelationRule."
            )

        return rule.enabled and getattr(event, "event_type", None) in rule.event_types

    def evaluate(self, session_id: str) -> list:
        """
        Evaluate every ENABLED rule against a session's currently
        recorded observation events, opening or extending one
        incident per matching rule.

        Returns:
            The incidents opened or extended by this call, in rule
            registration order

        Raises:
            ExecutionObservationCorrelationRuleError: If session_id
                is None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            events = self._event_service.history(session_id)
            results = []

            for rule_id in self._rule_ids_in_order:
                rule = self._rules_by_id[rule_id]

                matching_event_ids = [event.event_id for event in events if self.matches(rule, event)]

                if not matching_event_ids:
                    continue

                incident = self._correlate(rule_id, session_id, matching_event_ids, rule.severity)
                results.append(incident)

            return results

    def rules(self) -> list:
        """
        List every registered rule, in registration order.
        """

        with self._lock:
            return [self._rules_by_id[rule_id] for rule_id in self._rule_ids_in_order]

    def _correlate(self, rule_id: str, session_id: str, event_ids: list, severity: str):
        key = (rule_id, session_id)
        active_incidents = {incident.incident_id: incident for incident in self._incident_service.active(session_id)}
        existing_incident_id = self._incident_id_by_rule_and_session.get(key)

        if existing_incident_id is not None and existing_incident_id in active_incidents:
            incident = active_incidents[existing_incident_id]

            for event_id in event_ids:
                if event_id not in incident.event_ids:
                    incident = self._incident_service.add(existing_incident_id, event_id)

            return incident

        incident = self._incident_service.open(session_id, event_ids, severity=severity)
        self._incident_id_by_rule_and_session[key] = incident.incident_id

        return incident

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationCorrelationRuleError(f"Cannot use an empty or blank {field_name}.")
