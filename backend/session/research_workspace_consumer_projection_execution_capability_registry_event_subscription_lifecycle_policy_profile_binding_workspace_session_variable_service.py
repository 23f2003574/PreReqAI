from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_variable_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_variable import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariable,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_variable_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableSnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableService:
    """
    Gives each consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    execution session its own local key/value store, so the stages of
    a pipeline run can exchange runtime data with each other without
    that data ever touching the pipeline's own definition.

    The service's responsibility is variable storage, not pipeline
    execution. It does NOT run stages or decide what a stage reads or
    writes; it relies on the existing execution session service,
    given at construction time, only to confirm a session ID is
    genuinely known before its variable store is touched.

    Behavior:
    - Every session has its own isolated store; the same key in two
      different sessions never collides
    - put() overwrites whatever value, if any, was previously stored
      under a key
    - snapshot() captures every key/value pair a session currently
      holds; restore() replaces a session's entire store with a
      previously taken snapshot's contents
    - A snapshot may only be restored into the session it was taken
      from

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_session_service):
        """
        Args:
            execution_session_service: The service used to confirm a
                session ID is known before its variable store is
                touched. Any object exposing `session(session_id)`,
                raising if the session is unknown, is accepted
        """

        self._execution_session_service = execution_session_service
        self._variables_by_session_id = {}
        self._lock = RLock()

    def put(self, session_id: str, key: str, value) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariable:
        """
        Store a value under a key, overwriting whatever was
        previously stored under it.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError:
                If session_id or key is None or blank, or the
                execution session service does not recognize
                session_id
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(key, "key")

        with self._lock:
            self._ensure_session_known(session_id)

            variable = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariable(
                session_id=session_id,
                key=key,
                value=value,
                updated_at=datetime.now(timezone.utc),
            )

            self._variables_by_session_id.setdefault(session_id, {})[key] = variable

            return variable

    def get(self, session_id: str, key: str):
        """
        Look up a session's variable by key.

        Returns:
            The session's ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariable
            for that key, or None if no value has been put() under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError:
                If session_id or key is None or blank, or the
                execution session service does not recognize
                session_id
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(key, "key")

        with self._lock:
            self._ensure_session_known(session_id)

            return self._variables_by_session_id.get(session_id, {}).get(key)

    def remove(self, session_id: str, key: str) -> None:
        """
        Remove a session's variable by key, if it has one.

        Removing a key that was never put(), or already removed, is
        not an error.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError:
                If session_id or key is None or blank, or the
                execution session service does not recognize
                session_id
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(key, "key")

        with self._lock:
            self._ensure_session_known(session_id)

            self._variables_by_session_id.get(session_id, {}).pop(key, None)

    def snapshot(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableSnapshot:
        """
        Capture every key/value pair a session currently holds.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError:
                If session_id is None or blank, or the execution
                session service does not recognize it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            current = self._variables_by_session_id.get(session_id, {})

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableSnapshot(
                session_id=session_id,
                variables=MappingProxyType({key: variable.value for key, variable in current.items()}),
            )

    def restore(self, session_id: str, snapshot: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableSnapshot) -> None:
        """
        Replace a session's entire variable store with a previously
        taken snapshot's contents.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError:
                If session_id is None or blank, the execution session
                service does not recognize it, or snapshot is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableSnapshot
                taken from the same session
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            if not isinstance(snapshot, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableSnapshot):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError(
                    "Cannot restore an invalid session variable snapshot: snapshot must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableSnapshot."
                )

            if snapshot.session_id != session_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError(
                    f"Cannot restore a snapshot taken from session ID {snapshot.session_id!r} into session ID "
                    f"{session_id!r}."
                )

            now = datetime.now(timezone.utc)

            self._variables_by_session_id[session_id] = {
                key: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariable(
                    session_id=session_id,
                    key=key,
                    value=value,
                    updated_at=now,
                )
                for key, value in snapshot.variables.items()
            }

    def _ensure_session_known(self, session_id: str) -> None:
        try:
            self._execution_session_service.session(session_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError(
                f"No execution session is known under session ID {session_id!r}."
            ) from error

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionVariableError(
                f"Cannot operate with an empty or blank {label}."
            )
