from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_admission_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_admission_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_admission_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionService:
    """
    Decides whether a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session may start, weighing its assigned
    policy, available capacity, and whether it is already pending, so
    a session never starts in violation of those constraints.

    The service's responsibility is the admission decision, not
    session lifecycle or policy enforcement details. It does NOT
    start a session itself; a caller is expected to call admit()
    immediately before starting a session, and to decline to start it
    when the returned result is not accepted. It also does NOT define
    or store policies itself; it relies on the existing session policy
    service, given at construction time, to resolve and validate the
    policy assigned to a session.

    Behavior:
    - An accepted admission holds one of the service's capacity slots
      until it is explicitly released via reject()
    - A session with an admission already pending is rejected as a
      duplicate; admit() must not be called again for it until that
      pending admission is reject()-ed
    - A session whose requested policy_id does not match its actually
      assigned policy, or whose assigned policy fails validation, is
      rejected
    - Every decision, accepted or rejected, is recorded and is the
      value can_start() reports until a later decision replaces it

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, policy_service, capacity: int):
        """
        Args:
            policy_service: The service used to resolve and validate
                the policy assigned to a session. Any object exposing
                `policy(session_id)` and `validate(session_id)`,
                raising if the session has no valid assigned policy,
                is accepted
            capacity: The maximum number of sessions that may hold an
                accepted admission at the same time

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError:
                If capacity is not a positive integer
        """

        if capacity is None or isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError(
                f"Invalid admission capacity {capacity!r}; capacity must be a positive integer."
            )

        self._policy_service = policy_service
        self._capacity = capacity
        self._pending = {}
        self._results_by_session_id = {}
        self._lock = RLock()

    def admit(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionRequest,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionResult:
        """
        Decide whether a session may start, immediately before it is
        started.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError:
                If request is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionRequest
        """

        if not isinstance(request, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionRequest):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError(
                "Cannot admit an invalid request: request must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionRequest."
            )

        with self._lock:
            reason = self._rejection_reason(request)

            if reason is not None:
                result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionResult(
                    accepted=False,
                    reason=reason,
                )
            else:
                self._pending[request.session_id] = request

                result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionResult(
                    accepted=True,
                )

            self._results_by_session_id[request.session_id] = result

            return result

    def reject(
        self, session_id: str, reason: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionResult:
        """
        Explicitly refuse a session, freeing the capacity slot its
        admission held, if any.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError:
                If session_id or reason is None or blank
        """

        self._validate_id(session_id, "session ID")

        if reason is None or not reason.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError(
                "Cannot reject a session with an empty or blank reason."
            )

        with self._lock:
            self._pending.pop(session_id, None)

            result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionResult(
                accepted=False,
                reason=reason,
            )

            self._results_by_session_id[session_id] = result

            return result

    def can_start(self, session_id: str) -> bool:
        """
        Report whether a session's most recent admission decision was
        acceptance.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError:
                If session_id is None or blank, or no admission
                decision has ever been recorded for it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            result = self._results_by_session_id.get(session_id)

            if result is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError(
                    f"No admission decision has been recorded for session ID {session_id!r}."
                )

            return result.accepted

    def pending(self) -> tuple:
        """
        List every admission request currently holding a capacity
        slot.
        """

        with self._lock:
            return tuple(self._pending.values())

    def _rejection_reason(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionRequest,
    ) -> str:
        if request.session_id in self._pending:
            return f"session ID {request.session_id!r} already has a pending admission."

        policy_reason = self._policy_rejection_reason(request)

        if policy_reason is not None:
            return policy_reason

        if len(self._pending) >= self._capacity:
            return f"admission capacity of {self._capacity} session(s) is exhausted."

        return None

    def _policy_rejection_reason(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionRequest,
    ) -> str:
        try:
            policy = self._policy_service.policy(request.session_id)
        except Exception:
            return f"session ID {request.session_id!r} has no policy assigned."

        if policy.policy_id != request.policy_id:
            return (
                f"session ID {request.session_id!r} is governed by policy ID {policy.policy_id!r}, not the "
                f"requested policy ID {request.policy_id!r}."
            )

        try:
            self._policy_service.validate(request.session_id)
        except Exception as error:
            return str(error)

        return None

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAdmissionError(
                f"Cannot operate with an empty or blank {label}."
            )
