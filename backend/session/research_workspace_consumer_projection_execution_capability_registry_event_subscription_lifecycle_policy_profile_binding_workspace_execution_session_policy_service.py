from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_policy_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_policy_assignment import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyAssignment,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyService:
    """
    Registers reusable consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session policies and binds each session to at
    most one of them, so a session's allowed runtime, idle window, and
    restorability are governed independently of the session instance
    itself.

    The service's responsibility is policy registration, assignment,
    and validation, not session lifecycle. It does not start, finish,
    or cancel a session itself; a caller is expected to invoke
    validate(session_id) at the moment a session is about to be
    started, and to decline to start it if validate() raises.

    Behavior:
    - A registered policy is reusable: it may be assigned to any
      number of sessions
    - A session may have at most one active policy assignment at a
      time; assigning a new policy to a session replaces its prior
      assignment
    - A disabled policy cannot be assigned to a session
    - validate() fails for a session with no assigned policy, or whose
      assigned policy is disabled

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._policies_by_id = {}
        self._assignment_by_session_id = {}
        self._lock = RLock()

    def register(
        self,
        policy: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy:
        """
        Register a reusable session policy.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError:
                If a policy is already registered under policy.policy_id
        """

        with self._lock:
            if policy.policy_id in self._policies_by_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError(
                    f"Policy ID {policy.policy_id!r} is already registered."
                )

            self._policies_by_id[policy.policy_id] = policy

            return policy

    def assign(
        self, session_id: str, policy_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyAssignment:
        """
        Bind a session to a registered, enabled session policy,
        replacing any policy previously assigned to that session.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError:
                If session_id or policy_id is None or blank, no policy
                is registered under policy_id, or that policy is
                disabled
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(policy_id, "policy ID")

        with self._lock:
            policy = self._resolve_policy(policy_id)

            if not policy.enabled:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError(
                    f"Cannot assign policy ID {policy_id!r} to session ID {session_id!r}: policy is disabled."
                )

            assignment = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyAssignment(
                session_id=session_id,
                policy_id=policy_id,
            )

            self._assignment_by_session_id[session_id] = assignment

            return assignment

    def unassign(self, session_id: str) -> None:
        """
        Remove a session's current policy assignment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError:
                If session_id is None or blank, or no policy is
                currently assigned to it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._resolve_assignment(session_id)

            del self._assignment_by_session_id[session_id]

    def policy(
        self, session_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy:
        """
        Look up the policy currently governing a session.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError:
                If session_id is None or blank, no policy is currently
                assigned to it, or the assigned policy is no longer
                registered
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            assignment = self._resolve_assignment(session_id)

            return self._resolve_policy(assignment.policy_id)

    def validate(self, session_id: str) -> bool:
        """
        Confirm a session is governed by a registered, enabled policy,
        so it is safe to start. Intended to be called at the moment a
        session is about to be started, before it is marked active.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError:
                If session_id is None or blank, no policy is currently
                assigned to it, the assigned policy is no longer
                registered, or that policy is disabled
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            policy = self.policy(session_id)

            if not policy.enabled:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError(
                    f"Cannot start session ID {session_id!r}: assigned policy ID {policy.policy_id!r} is disabled."
                )

            return True

    def _resolve_policy(
        self, policy_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy:
        policy = self._policies_by_id.get(policy_id)

        if policy is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError(
                f"No session policy is registered under policy ID {policy_id!r}."
            )

        return policy

    def _resolve_assignment(
        self, session_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyAssignment:
        assignment = self._assignment_by_session_id.get(session_id)

        if assignment is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError(
                f"No session policy is assigned to session ID {session_id!r}."
            )

        return assignment

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError(
                f"Cannot operate with an empty or blank {label}."
            )
