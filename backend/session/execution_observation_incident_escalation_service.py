from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .execution_observation_escalation_policy_error import (
    ExecutionObservationEscalationPolicyError,
)

from .execution_observation_escalation_policy import (
    ExecutionObservationEscalationPolicy,
)

_ESCALATION_ACTOR = "escalation-policy"


class ExecutionObservationIncidentEscalationService:
    """
    Automatically escalates incidents when their severity and time
    spent unescalated cross a configured policy's threshold. An
    incident's core data and its lifecycle status are assumed to
    already exist in the injected services; this service only reads
    from them and, on a breach, calls into the lifecycle service to
    perform the escalation itself.

    Behavior:
    - evaluate() only considers an incident whose underlying record
      is currently ACTIVE and whose lifecycle status is currently
      ACKNOWLEDGED; an OPEN, already-ESCALATED, or RESOLVED incident
      is left untouched, so an already-escalated incident is never
      re-escalated
    - evaluate() only considers ENABLED policies whose severity
      matches the incident's severity; a breach is the time elapsed
      since the incident opened being at or beyond a matching
      policy's timeout_seconds (a timeout_seconds of 0 makes any
      severity match an immediate breach)
    - escalated() reports whether an incident's current lifecycle
      status is ESCALATED

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, incident_service, lifecycle_service):
        """
        Args:
            incident_service: The service used to read an incident's
                core data. Any object exposing `get(incident_id)`,
                returning a record with `severity`, `status`
                (ACTIVE/RESOLVED), and `opened_at` attributes and
                raising if incident_id is unknown, is accepted
            lifecycle_service: The service used to read and advance
                an incident's lifecycle status. Any object exposing
                `status(incident_id)` and `escalate(incident_id,
                actor)` is accepted
        """

        self._incident_service = incident_service
        self._lifecycle_service = lifecycle_service
        self._policies_by_id = {}
        self._policy_ids_in_order = []
        self._lock = RLock()

    def register(self, policy: ExecutionObservationEscalationPolicy) -> ExecutionObservationEscalationPolicy:
        """
        Register a new escalation policy.

        Raises:
            ExecutionObservationEscalationPolicyError: If policy is
                not an ExecutionObservationEscalationPolicy, or its
                policy ID is already registered
        """

        if not isinstance(policy, ExecutionObservationEscalationPolicy):
            raise ExecutionObservationEscalationPolicyError(
                "Cannot register an invalid policy: policy must be an ExecutionObservationEscalationPolicy."
            )

        with self._lock:
            if policy.policy_id in self._policies_by_id:
                raise ExecutionObservationEscalationPolicyError(
                    f"Policy ID {policy.policy_id!r} is already registered."
                )

            self._policies_by_id[policy.policy_id] = policy
            self._policy_ids_in_order.append(policy.policy_id)

            return policy

    def evaluate(self, incident_id: str):
        """
        Evaluate every ENABLED policy against an incident, escalating
        it through the lifecycle service on the first breaching
        policy found.

        Returns:
            The resulting transition if the incident was escalated,
            None otherwise

        Raises:
            ExecutionObservationEscalationPolicyError: If incident_id
                is None or blank
        """

        self._validate_id(incident_id, "incident ID")

        with self._lock:
            incident = self._incident_service.get(incident_id)

            if getattr(incident, "status", None) != "ACTIVE":
                return None

            if self._lifecycle_service.status(incident_id) != "ACKNOWLEDGED":
                return None

            now = datetime.now(timezone.utc)

            for policy_id in self._policy_ids_in_order:
                policy = self._policies_by_id[policy_id]

                if not policy.enabled or policy.severity != incident.severity:
                    continue

                elapsed_seconds = (now - incident.opened_at).total_seconds()

                if elapsed_seconds >= policy.timeout_seconds:
                    return self._lifecycle_service.escalate(incident_id, _ESCALATION_ACTOR)

            return None

    def escalated(self, incident_id: str) -> bool:
        """
        Report whether an incident's current lifecycle status is
        ESCALATED.

        Raises:
            ExecutionObservationEscalationPolicyError: If incident_id
                is None or blank
        """

        self._validate_id(incident_id, "incident ID")

        return self._lifecycle_service.status(incident_id) == "ESCALATED"

    def policies(self) -> list:
        """
        List every registered policy, in registration order.
        """

        with self._lock:
            return [self._policies_by_id[policy_id] for policy_id in self._policy_ids_in_order]

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationEscalationPolicyError(f"Cannot use an empty or blank {field_name}.")
