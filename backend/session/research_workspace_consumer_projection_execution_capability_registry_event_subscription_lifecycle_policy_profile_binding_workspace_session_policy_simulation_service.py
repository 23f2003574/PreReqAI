from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_simulation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_simulation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulation,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_simulation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationResult,
)

_MISSING = object()


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationService:
    """
    Estimates the impact of a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session policy version against real
    sessions before it is rolled out, entirely read-only, so a
    caller can preview a rollout's effect without changing any
    session's actual, runtime-governing state.

    The service's responsibility is estimation and reporting, not
    enforcement or rollout. It does NOT resolve, bind, or otherwise
    mutate any session's real policy resolution; it relies on the
    existing session policy service and session policy version
    service, both given at construction time, purely for read-only
    lookups, and on an evaluator, also given at construction time, to
    decide whether a session would pass under a given configuration.

    Behavior:
    - Every simulate() and simulate_sessions() call is read-only: it
      never resolves, assigns, publishes, or rolls back anything in
      the services it depends on
    - A simulation's report() is retained exactly as it was produced
      until discard()-ed; nothing else in the service invalidates or
      overwrites it
    - simulate_sessions() requires every given session to share the
      same assigned policy, so the simulation has one unambiguous
      target version to evaluate against

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, policy_service, policy_version_service, sessions_provider, evaluator):
        """
        Args:
            policy_service: The service used to resolve which policy
                governs a session, read-only. Any object exposing
                `policy(session_id)`, raising if the session has no
                assigned policy, is accepted
            policy_version_service: The service used to look up a
                policy's latest published version, read-only. Any
                object exposing `latest(policy_id)`, raising if none
                has been published, is accepted
            sessions_provider: A zero-argument callable returning
                every session_id currently known, used by simulate()
                to evaluate a policy against every session
            evaluator: A callable(configuration, session_id) -> bool
                deciding whether a session would pass under a given
                configuration
        """

        self._policy_service = policy_service
        self._policy_version_service = policy_version_service
        self._sessions_provider = sessions_provider
        self._evaluator = evaluator
        self._simulations_by_id = {}
        self._results_by_id = {}
        self._lock = RLock()

    def simulate(
        self, policy_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulation:
        """
        Run a read-only simulation of a policy's latest published
        version against every currently known session, immediately
        before previewing a rollout of that version.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError:
                If policy_id is None or blank, or no version has ever
                been published for it
        """

        self._validate_id(policy_id, "policy ID")

        version = self._latest_version(policy_id)
        session_ids = tuple(self._sessions_provider())

        with self._lock:
            return self._run(policy_id, version, session_ids)

    def simulate_sessions(
        self, session_ids
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulation:
        """
        Run a read-only simulation of a policy's latest published
        version against an explicit set of sessions.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError:
                If session_ids is empty, any session has no assigned
                policy, the given sessions do not all share the same
                assigned policy, or no version has ever been
                published for that policy
        """

        session_ids = tuple(session_ids)

        if not session_ids:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                "Cannot simulate an empty set of sessions."
            )

        policy_ids = set()

        for session_id in session_ids:
            try:
                policy_ids.add(self._policy_service.policy(session_id).policy_id)
            except Exception as error:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                    f"Session ID {session_id!r} has no assigned policy."
                ) from error

        if len(policy_ids) != 1:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                "Cannot simulate sessions governed by more than one policy in a single call."
            )

        policy_id = next(iter(policy_ids))
        version = self._latest_version(policy_id)

        with self._lock:
            return self._run(policy_id, version, session_ids)

    def report(
        self, simulation_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationResult:
        """
        Read back a retained simulation's result.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError:
                If simulation_id is None or blank, or no simulation is
                retained under it
        """

        self._validate_id(simulation_id, "simulation ID")

        with self._lock:
            result = self._results_by_id.get(simulation_id)

            if result is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                    f"No simulation is retained under simulation ID {simulation_id!r}."
                )

            return result

    def compare(
        self,
        version_a: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion,
        version_b: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion,
    ) -> tuple:
        """
        List the configuration fields that differ between two policy
        versions.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError:
                If version_a or version_b is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion
        """

        for version, label in ((version_a, "version_a"), (version_b, "version_b")):
            if not isinstance(version, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                    f"Cannot compare an invalid {label}: {label} must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion."
                )

        keys = set(version_a.configuration) | set(version_b.configuration)

        return tuple(
            sorted(
                key
                for key in keys
                if version_a.configuration.get(key, _MISSING) != version_b.configuration.get(key, _MISSING)
            )
        )

    def discard(self, simulation_id: str) -> None:
        """
        Permanently discard a retained simulation and its report.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError:
                If simulation_id is None or blank, or no simulation is
                retained under it
        """

        self._validate_id(simulation_id, "simulation ID")

        with self._lock:
            if simulation_id not in self._simulations_by_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                    f"No simulation is retained under simulation ID {simulation_id!r}."
                )

            del self._simulations_by_id[simulation_id]
            del self._results_by_id[simulation_id]

    def _run(
        self,
        policy_id: str,
        version: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion,
        session_ids: tuple,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulation:
        passed = tuple(
            session_id for session_id in session_ids if self._evaluator(version.configuration, session_id)
        )
        failed = tuple(session_id for session_id in session_ids if session_id not in passed)

        simulation = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulation(
            simulation_id=str(uuid4()),
            policy_id=policy_id,
            target_version=version.version,
            session_ids=session_ids,
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationResult(
            affected=session_ids,
            passed=passed,
            failed=failed,
        )

        self._simulations_by_id[simulation.simulation_id] = simulation
        self._results_by_id[simulation.simulation_id] = result

        return simulation

    def _latest_version(
        self, policy_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion:
        try:
            return self._policy_version_service.latest(policy_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                f"No version has ever been published for policy ID {policy_id!r}."
            ) from error

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError(
                f"Cannot operate with an empty or blank {label}."
            )
