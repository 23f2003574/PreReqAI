from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_checkpoint_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_checkpoint import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpoint,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_restore_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRestoreResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointService:
    """
    Lets a consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    session save recoverable checkpoints of its runtime state, so an
    interrupted run can resume from its last saved point instead of
    restarting from the beginning.

    The service's responsibility is checkpoint storage and retrieval,
    not pipeline execution. It does NOT run stages, decide when a
    checkpoint should be taken, or apply a restored state back onto a
    running pipeline; it relies on the existing execution session
    service, given at construction time, only to confirm a session ID
    is genuinely known and to check whether a session is still active
    before restoring into it.

    Behavior:
    - A checkpoint is meant to be taken by its caller after a stage
      finishes successfully; this service does not itself decide
      when that is
    - Checkpoints are immutable once created: restoring or removing
      one never mutates it or any other checkpoint
    - Every checkpoint taken for a session is preserved in creation
      order until individually removed, forming that session's full
      checkpoint history
    - latest() returns the most recently created checkpoint for a
      session, which is what a resume should restore from

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_session_service):
        """
        Args:
            execution_session_service: The service used to confirm a
                session ID is known and to check a session's current
                status. Any object exposing `session(session_id)`,
                raising if the session is unknown and otherwise
                returning an object with a `status` attribute whose
                value has a `.value` attribute, is accepted
        """

        self._execution_session_service = execution_session_service
        self._checkpoints = {}
        self._checkpoint_ids_by_session_id = {}
        self._lock = RLock()

    def create(self, session_id: str, stage_id: str, state) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpoint:
        """
        Save a new checkpoint of a session's runtime state.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError:
                If session_id or stage_id is None or blank, state is
                not a mapping, the execution session service does not
                recognize session_id, or the generated checkpoint ID
                is already registered
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(stage_id, "stage ID")

        with self._lock:
            self._ensure_session_known(session_id)

            checkpoint_id = str(uuid4())

            if checkpoint_id in self._checkpoints:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError(
                    f"Checkpoint ID {checkpoint_id!r} is already registered."
                )

            checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpoint(
                checkpoint_id=checkpoint_id,
                session_id=session_id,
                stage_id=stage_id,
                state=state,
                created_at=datetime.now(timezone.utc),
            )

            self._checkpoints[checkpoint_id] = checkpoint
            self._checkpoint_ids_by_session_id.setdefault(session_id, []).append(checkpoint_id)

            return checkpoint

    def restore(self, checkpoint_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRestoreResult:
        """
        Restore a session from one of its checkpoints.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError:
                If checkpoint_id is None or blank, no checkpoint is
                registered under it, or the checkpoint's session is
                not active
        """

        self._validate_id(checkpoint_id, "checkpoint ID")

        with self._lock:
            checkpoint = self._resolve_checkpoint(checkpoint_id)
            session = self._ensure_session_known(checkpoint.session_id)

            if session.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus.ACTIVE:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError(
                    f"Cannot restore checkpoint ID {checkpoint_id!r}: session ID {checkpoint.session_id!r} is "
                    f"{session.status.value}, not active."
                )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRestoreResult(
                session_id=checkpoint.session_id,
                checkpoint_id=checkpoint_id,
                restored=True,
            )

    def latest(self, session_id: str):
        """
        Look up the most recently created checkpoint for a session.

        Returns:
            The session's latest checkpoint, or None if it has none

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError:
                If session_id is None or blank, or the execution
                session service does not recognize it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            checkpoint_ids = self._checkpoint_ids_by_session_id.get(session_id, [])

            if not checkpoint_ids:
                return None

            return self._checkpoints[checkpoint_ids[-1]]

    def history(self, session_id: str) -> tuple:
        """
        List every checkpoint taken for a session, oldest first.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError:
                If session_id is None or blank, or the execution
                session service does not recognize it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            return tuple(
                self._checkpoints[checkpoint_id]
                for checkpoint_id in self._checkpoint_ids_by_session_id.get(session_id, [])
            )

    def remove(self, checkpoint_id: str) -> None:
        """
        Remove a checkpoint, without affecting any other checkpoint.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError:
                If checkpoint_id is None or blank, or no checkpoint is
                registered under it
        """

        self._validate_id(checkpoint_id, "checkpoint ID")

        with self._lock:
            checkpoint = self._resolve_checkpoint(checkpoint_id)

            del self._checkpoints[checkpoint_id]

            session_checkpoint_ids = self._checkpoint_ids_by_session_id.get(checkpoint.session_id)

            if session_checkpoint_ids is not None:
                session_checkpoint_ids.remove(checkpoint_id)

    def _ensure_session_known(self, session_id: str):
        try:
            return self._execution_session_service.session(session_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError(
                f"No execution session is known under session ID {session_id!r}."
            ) from error

    def _resolve_checkpoint(self, checkpoint_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpoint:
        checkpoint = self._checkpoints.get(checkpoint_id)

        if checkpoint is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError(
                f"No session checkpoint is registered under checkpoint ID {checkpoint_id!r}."
            )

        return checkpoint

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError(
                f"Cannot operate with an empty or blank {label}."
            )
