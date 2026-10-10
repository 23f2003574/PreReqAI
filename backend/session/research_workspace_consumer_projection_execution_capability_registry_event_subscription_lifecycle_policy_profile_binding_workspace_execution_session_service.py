from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSession,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService:
    """
    Isolates a single consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace pipeline run behind an execution session, so its
    runtime state, ownership, and lifecycle are tracked independently
    of the pipeline's own definition.

    The service's responsibility is session lifecycle, not pipeline
    execution. It does NOT run a pipeline's stages itself; it relies
    on the existing execution pipeline service, given at construction
    time, only to confirm a pipeline ID is genuinely known before a
    session is opened for it.

    Behavior:
    - A pipeline may have at most one active session at a time;
      starting a second session for a pipeline that already has one
      active is rejected
    - finish() releases the runtime state a session owns: once
      finished, the pipeline it tracked is free to start a new
      session
    - cancel() likewise releases the session's runtime state, without
      recording a successful/unsuccessful outcome
    - A cancelled or finished session remains queryable through
      session(); it is simply no longer active

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_pipeline_service):
        """
        Args:
            execution_pipeline_service: The service used to confirm a
                pipeline ID is known before a session is started for
                it. Any object exposing `status(pipeline_id)`, raising
                if the pipeline is unknown, is accepted
        """

        self._execution_pipeline_service = execution_pipeline_service
        self._sessions = {}
        self._active_session_id_by_pipeline_id = {}
        self._lock = RLock()

    def start(self, pipeline_id: str, owner: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSession:
        """
        Open a new active execution session for a pipeline.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError:
                If pipeline_id or owner is None or blank, the
                execution pipeline service does not recognize
                pipeline_id, or the pipeline already has an active
                session
        """

        self._validate_id(pipeline_id, "pipeline ID")
        self._validate_id(owner, "owner")

        with self._lock:
            self._ensure_pipeline_known(pipeline_id)

            if pipeline_id in self._active_session_id_by_pipeline_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                    f"Cannot start an execution session for pipeline ID {pipeline_id!r}: an active session "
                    "already exists for it."
                )

            session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSession(
                session_id=str(uuid4()),
                pipeline_id=pipeline_id,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus.ACTIVE,
                owner=owner,
                started_at=datetime.now(timezone.utc),
                finished_at=None,
            )

            self._sessions[session.session_id] = session
            self._active_session_id_by_pipeline_id[pipeline_id] = session.session_id

            return session

    def finish(self, session_id: str, successful: bool) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionResult:
        """
        Finish an active execution session, releasing the runtime
        state it owns.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError:
                If session_id is None or blank, no session is
                registered under it, or the session is not active
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            session = self._resolve_session(session_id)

            if session.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus.ACTIVE:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                    f"Cannot finish execution session ID {session_id!r}: session is {session.status.value}, "
                    "not active."
                )

            finished = replace(
                session,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus.FINISHED,
                finished_at=datetime.now(timezone.utc),
            )

            self._sessions[session_id] = finished
            self._active_session_id_by_pipeline_id.pop(session.pipeline_id, None)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionResult(
                session_id=session_id,
                successful=successful,
            )

    def cancel(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSession:
        """
        Cancel an active execution session, releasing the runtime
        state it owns without recording a successful/unsuccessful
        outcome.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError:
                If session_id is None or blank, no session is
                registered under it, or the session is not active
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            session = self._resolve_session(session_id)

            if session.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus.ACTIVE:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                    f"Cannot cancel execution session ID {session_id!r}: session is {session.status.value}, "
                    "not active."
                )

            cancelled = replace(
                session,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus.CANCELLED,
                finished_at=datetime.now(timezone.utc),
            )

            self._sessions[session_id] = cancelled
            self._active_session_id_by_pipeline_id.pop(session.pipeline_id, None)

            return cancelled

    def session(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSession:
        """
        Look up a session's current state, regardless of whether it
        is active, finished, or cancelled.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError:
                If session_id is None or blank, or no session is
                registered under it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return self._resolve_session(session_id)

    def active(self) -> tuple:
        """
        List every currently active session, one per pipeline with a
        session open.
        """

        with self._lock:
            return tuple(
                self._sessions[session_id] for session_id in self._active_session_id_by_pipeline_id.values()
            )

    def _ensure_pipeline_known(self, pipeline_id: str) -> None:
        try:
            self._execution_pipeline_service.status(pipeline_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                f"No pipeline is known under pipeline ID {pipeline_id!r}."
            ) from error

    def _resolve_session(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSession:
        session = self._sessions.get(session_id)

        if session is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                f"No execution session is registered under session ID {session_id!r}."
            )

        return session

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError(
                f"Cannot operate with an empty or blank {label}."
            )
