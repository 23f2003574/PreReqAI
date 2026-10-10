from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_audit_event import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditEvent,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_drift_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyDriftResult,
)

_MISSING = object()


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditService:
    """
    Maintains an append-only audit log of consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace execution session policy
    evaluation, and detects when a session's actual, effective
    configuration has drifted from its approved, published policy
    version.

    The service's responsibility is auditing and drift detection, not
    policy evaluation itself. It relies on the existing session
    policy version service, given at construction time, to establish
    which approved policy version governs a session, and on an
    actual_configuration_provider, also given at construction time, to
    read a session's real, currently effective configuration.

    Behavior:
    - The audit log is append-only: record() only ever adds an event;
      nothing already recorded is ever modified, and only purge()
      ever removes anything
    - detect_drift() always records the event it produces, "COMPLIANT"
      or "DRIFT_DETECTED", as a side effect of the check itself
    - history() returns a session's events newest first
    - purge() removes every event, across every session, older than a
      given timestamp

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, policy_version_service, actual_configuration_provider):
        """
        Args:
            policy_version_service: The service used to establish
                which approved policy version governs a session. Any
                object exposing `resolve(session_id)`, returning an
                object with `policy_id` and `version` attributes, and
                `history(policy_id)`, returning an iterable of objects
                with `version` and `configuration` attributes, is
                accepted
            actual_configuration_provider: A callable(session_id) ->
                dict returning a session's actual, currently
                effective configuration
        """

        self._policy_version_service = policy_version_service
        self._actual_configuration_provider = actual_configuration_provider
        self._events_by_session_id = {}
        self._lock = RLock()

    def record(
        self,
        event: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditEvent,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditEvent:
        """
        Append an event to the audit log, immediately whenever
        existing policy evaluation produces something worth recording.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError:
                If event is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditEvent
        """

        if not isinstance(event, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditEvent):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                "Cannot record an invalid event: event must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditEvent."
            )

        with self._lock:
            self._events_by_session_id.setdefault(event.session_id, []).append(event)

            return event

    def detect_drift(
        self, session_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyDriftResult:
        """
        Compare a session's actual, effective configuration against
        its approved policy version, immediately as part of existing
        policy evaluation, recording the outcome as an audit event.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError:
                If session_id is None or blank, the session has no
                approved policy version, or its approved
                configuration cannot be found
        """

        self._validate_id(session_id, "session ID")

        try:
            resolution = self._policy_version_service.resolve(session_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                f"Session ID {session_id!r} has no approved policy version."
            ) from error

        approved_configuration = self._approved_configuration(resolution.policy_id, resolution.version)
        actual_configuration = self._actual_configuration_provider(session_id)

        keys = set(approved_configuration) | set(actual_configuration)
        differences = tuple(
            sorted(
                key
                for key in keys
                if approved_configuration.get(key, _MISSING) != actual_configuration.get(key, _MISSING)
            )
        )
        compliant = not differences

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyDriftResult(
            session_id=session_id,
            compliant=compliant,
            differences=differences,
        )

        with self._lock:
            self.record(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditEvent(
                    event_id=str(uuid4()),
                    session_id=session_id,
                    policy_id=resolution.policy_id,
                    version=resolution.version,
                    event_type="COMPLIANT" if compliant else "DRIFT_DETECTED",
                    timestamp=datetime.now(timezone.utc),
                )
            )

        return result

    def history(self, session_id: str) -> tuple:
        """
        List every audit event recorded for a session, newest first.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError:
                If session_id is None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return tuple(reversed(self._events_by_session_id.get(session_id, [])))

    def latest(
        self, session_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditEvent:
        """
        Look up the most recently recorded audit event for a session.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError:
                If session_id is None or blank, or no event has ever
                been recorded for it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            events = self._events_by_session_id.get(session_id, [])

            if not events:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                    f"No audit event has ever been recorded for session ID {session_id!r}."
                )

            return events[-1]

    def purge(self, before_timestamp: datetime) -> int:
        """
        Permanently remove every audit event, across every session,
        older than before_timestamp.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError:
                If before_timestamp is not a datetime
        """

        if before_timestamp is None or not isinstance(before_timestamp, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                "Cannot purge with a non-datetime before_timestamp."
            )

        with self._lock:
            purged = 0

            for session_id in list(self._events_by_session_id.keys()):
                events = self._events_by_session_id[session_id]
                kept = [event for event in events if event.timestamp >= before_timestamp]
                purged += len(events) - len(kept)

                if kept:
                    self._events_by_session_id[session_id] = kept
                else:
                    del self._events_by_session_id[session_id]

            return purged

    def _approved_configuration(self, policy_id: str, version: int) -> dict:
        try:
            versions = self._policy_version_service.history(policy_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                f"No version history is available for policy ID {policy_id!r}."
            ) from error

        for candidate in versions:
            if candidate.version == version:
                return candidate.configuration

        raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
            f"No version {version!r} was found in the history of policy ID {policy_id!r}."
        )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                f"Cannot operate with an empty or blank {label}."
            )
