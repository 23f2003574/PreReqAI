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

from .execution_runtime_handoff import (
    ExecutionRuntimeHandoff,
    STATUS_ACCEPTED,
    STATUS_PENDING,
    STATUS_REJECTED,
)

from .execution_runtime_handoff_error import (
    ExecutionRuntimeHandoffError,
)

INTERRUPTED_STATES = ("FAILED",)


class ExecutionRuntimeHandoffService:
    """
    Hands off an interrupted runtime to recovery infrastructure with
    enough state to resume safely.

    Composes with:
    - an existing runtime state service (anything exposing
      `state(runtime_id) -> object with .state`, matching
      ExecutionRuntimeStateService), used to confirm a runtime is
      currently interrupted (FAILED) before it can be handed off
    - an existing checkpoint infrastructure (anything exposing
      `valid(checkpoint_id) -> bool`), used to confirm the checkpoint
      a handoff names actually exists and is usable

    Behavior:
    - create() admits a new PENDING handoff, but only for a runtime
      that is currently FAILED and a checkpoint that is currently
      valid
    - accept() decides a handoff ACCEPTED, but only while it is still
      PENDING; once ACCEPTED, a handoff is immutable and accept() on
      it again is rejected rather than treated as a no-op
    - reject() decides a handoff REJECTED (recording the rejection
      reason), but only while it is still PENDING, keeping invalid
      handoffs out of recovery
    - status() reports a handoff's current status

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, state_service, checkpoint_service):
        self._state_service = state_service
        self._checkpoint_service = checkpoint_service
        self._handoffs_by_id = {}
        self._lock = RLock()

    def create(self, runtime_id: str, checkpoint_id: str, reason: str) -> ExecutionRuntimeHandoff:
        """
        Create a recovery handoff for runtime_id at checkpoint_id.

        Raises:
            ExecutionRuntimeHandoffError: If runtime_id, checkpoint_id,
                or reason is None or blank, runtime_id is unknown or
                not currently FAILED, or checkpoint_id is not valid
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(checkpoint_id, "checkpoint ID")
        self._validate_text(reason, "reason")

        try:
            current = self._state_service.state(runtime_id)
        except Exception as error:
            raise ExecutionRuntimeHandoffError(
                f"Cannot hand off runtime ID {runtime_id!r}: it is unknown."
            ) from error

        if current.state not in INTERRUPTED_STATES:
            raise ExecutionRuntimeHandoffError(
                f"Cannot hand off runtime ID {runtime_id!r}: it is not interrupted "
                f"(state is {current.state!r})."
            )

        try:
            checkpoint_is_valid = self._checkpoint_service.valid(checkpoint_id)
        except Exception as error:
            raise ExecutionRuntimeHandoffError(
                f"Cannot hand off runtime ID {runtime_id!r}: checkpoint ID {checkpoint_id!r} is unknown."
            ) from error

        if not checkpoint_is_valid:
            raise ExecutionRuntimeHandoffError(
                f"Cannot hand off runtime ID {runtime_id!r}: checkpoint ID {checkpoint_id!r} is not valid."
            )

        with self._lock:
            handoff = ExecutionRuntimeHandoff(
                handoff_id=str(uuid4()),
                runtime_id=runtime_id,
                checkpoint_id=checkpoint_id,
                reason=reason,
                status=STATUS_PENDING,
                created_at=datetime.now(timezone.utc),
            )

            self._handoffs_by_id[handoff.handoff_id] = handoff

            return handoff

    def accept(self, handoff_id: str) -> ExecutionRuntimeHandoff:
        """
        Accept a pending handoff, making it immutable.

        Raises:
            ExecutionRuntimeHandoffError: If handoff_id is None or
                blank, no handoff is registered under it, or it is
                not currently PENDING
        """

        self._validate_text(handoff_id, "handoff ID")

        with self._lock:
            handoff = self._resolve(handoff_id)

            if handoff.status != STATUS_PENDING:
                raise ExecutionRuntimeHandoffError(
                    f"Cannot accept handoff ID {handoff_id!r}: it is not pending "
                    f"(status is {handoff.status!r})."
                )

            accepted = replace(handoff, status=STATUS_ACCEPTED)
            self._handoffs_by_id[handoff_id] = accepted

            return accepted

    def reject(self, handoff_id: str, reason: str) -> ExecutionRuntimeHandoff:
        """
        Reject a pending handoff, recording why.

        Raises:
            ExecutionRuntimeHandoffError: If handoff_id or reason is
                None or blank, no handoff is registered under
                handoff_id, or it is not currently PENDING
        """

        self._validate_text(handoff_id, "handoff ID")
        self._validate_text(reason, "reason")

        with self._lock:
            handoff = self._resolve(handoff_id)

            if handoff.status != STATUS_PENDING:
                raise ExecutionRuntimeHandoffError(
                    f"Cannot reject handoff ID {handoff_id!r}: it is not pending "
                    f"(status is {handoff.status!r})."
                )

            rejected = replace(handoff, status=STATUS_REJECTED, reason=reason)
            self._handoffs_by_id[handoff_id] = rejected

            return rejected

    def status(self, handoff_id: str) -> str:
        """
        The current status of a handoff.

        Raises:
            ExecutionRuntimeHandoffError: If handoff_id is None or
                blank, or no handoff is registered under it
        """

        self._validate_text(handoff_id, "handoff ID")

        with self._lock:
            return self._resolve(handoff_id).status

    def _resolve(self, handoff_id: str) -> ExecutionRuntimeHandoff:
        handoff = self._handoffs_by_id.get(handoff_id)

        if handoff is None:
            raise ExecutionRuntimeHandoffError(
                f"No handoff is recorded under handoff ID {handoff_id!r}."
            )

        return handoff

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeHandoffError(f"Cannot use an empty or blank {field_name}.")
